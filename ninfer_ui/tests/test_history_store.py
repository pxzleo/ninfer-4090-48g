from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time as system_time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path


UI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI_ROOT))

from history_store import HistoryStore  # noqa: E402


@contextmanager
def local_timezone(name: str):
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    system_time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        system_time.tzset()


class HistoryStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temporary.name) / "history.sqlite3")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_realtime_keeps_only_five_minutes(self) -> None:
        now = 1_800_000_000_000
        self.store.record(now - 301_000, 10.0, 20.0)
        self.store.record(now - 2_000, 30.0, 40.0)
        self.store.record(now, 50.0, 60.0)

        result = self.store.query("realtime", now)

        self.assertEqual([row["decode"] for row in result["samples"]], [30.0, 50.0])
        self.assertEqual(result["label"], "最近5分钟 · 2秒采样")

    def test_aggregate_history_survives_reopen_within_retention(self) -> None:
        old = 1_700_000_000_000
        much_later = old + 300 * 24 * 60 * 60_000
        self.store.record(old, 12.0, 24.0)
        self.store.record(much_later, 36.0, 48.0)

        reopened = HistoryStore(self.store.path)
        result = reopened.query("day", old)

        self.assertTrue(result["samples"])
        self.assertEqual(max(row["decode"] for row in result["samples"]), 12.0)

    def test_aggregate_history_expires_after_400_days(self) -> None:
        old = 1_700_000_000_000
        self.store.record(old, 12.0, 24.0)
        self.store.record(old + 401 * 24 * 60 * 60_000, 36.0, 48.0)

        self.assertEqual(self.store.query("day", old)["samples"], [])

    def test_aggregate_history_keeps_full_boundary_minute_at_400_days(self) -> None:
        old = 1_700_000_058_999
        self.store.record(old, 12.0, 24.0)
        self.store.record(old + 400 * 24 * 60 * 60_000, 36.0, 48.0)

        self.assertTrue(self.store.query("day", old)["samples"])

    def test_clear_range_removes_selected_dates_only(self) -> None:
        first = self.store.query("day", 1_800_000_000_000)
        second = self.store.query("day", first["end_ms"] + 60_000)
        self.store.record(first["start_ms"] + 60_000, 10.0, 20.0)
        self.store.record(second["start_ms"] + 60_000, 30.0, 40.0)

        deleted = self.store.clear_range(first["start_ms"], first["end_ms"])

        self.assertEqual(deleted["aggregate_rows"], 1)
        self.assertEqual(self.store.query("day", first["start_ms"])["samples"], [])
        self.assertTrue(self.store.query("day", second["start_ms"])["samples"])

    def test_clear_dates_uses_server_local_calendar_boundaries(self) -> None:
        with local_timezone("America/New_York"):
            selected = self.store.query(
                "day", int(datetime(2026, 3, 8, 12).timestamp() * 1000)
            )
            self.store.record(selected["start_ms"] + 60_000, 10.0, 20.0)
            self.store.record(selected["end_ms"] + 60_000, 30.0, 40.0)

            deleted = self.store.clear_dates("2026-03-08", "2026-03-08")

            self.assertEqual(deleted["aggregate_rows"], 1)
            self.assertEqual(self.store.query("day", selected["start_ms"])["samples"], [])
            self.assertTrue(self.store.query("day", selected["end_ms"])["samples"])

    def test_day_uses_weighted_five_minute_buckets(self) -> None:
        now = 1_800_000_000_000
        bucket = now // 300_000 * 300_000
        self.store.record(bucket + 1_000, 10.0, 100.0)
        self.store.record(bucket + 61_000, 30.0, 300.0)

        result = self.store.query("day", now + 120_000)

        self.assertEqual(len(result["samples"]), 3)
        self.assertEqual(result["samples"][0]["decode"], 20.0)
        self.assertEqual(result["samples"][0]["prefill"], 200.0)
        self.assertEqual(max(row["decode"] for row in result["samples"]), 30.0)
        self.assertEqual(max(row["prefill"] for row in result["samples"]), 300.0)

    def test_day_preserves_short_peak_when_compressed(self) -> None:
        now = 1_800_000_000_000
        bucket = now // 300_000 * 300_000
        self.store.record(bucket + 1_000, 0.0, 0.0)
        self.store.record(bucket + 61_000, 120.0, 2400.0)
        self.store.record(bucket + 121_000, 0.0, 0.0)

        result = self.store.query("day", now + 180_000)

        self.assertEqual(max(row["decode"] for row in result["samples"]), 120.0)
        self.assertEqual(max(row["prefill"] for row in result["samples"]), 2400.0)

    def test_existing_average_table_migrates_before_peak_samples(self) -> None:
        path = Path(self.temporary.name) / "legacy.sqlite3"
        timestamp = 1_800_000_000_000
        minute = timestamp // 60_000 * 60_000
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE throughput_raw (timestamp_ms INTEGER PRIMARY KEY, decode_rate REAL NOT NULL, prefill_rate REAL NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE throughput_minute (bucket_ms INTEGER PRIMARY KEY, decode_sum REAL NOT NULL, prefill_sum REAL NOT NULL, sample_count INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO throughput_minute VALUES (?, 20, 200, 2)", (minute,)
            )

        store = HistoryStore(path)
        store.record(timestamp + 61_000, 120.0, 2400.0)
        result = store.query("day", timestamp + 180_000)

        self.assertEqual(max(row["decode"] for row in result["samples"]), 120.0)
        self.assertEqual(max(row["prefill"] for row in result["samples"]), 2400.0)
        with sqlite3.connect(path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(throughput_minute)")}
        self.assertTrue(
            {"decode_peak", "decode_peak_ms", "prefill_peak", "prefill_peak_ms"}
            <= columns
        )

    def test_first_database_initialization_is_thread_safe(self) -> None:
        store = HistoryStore(Path(self.temporary.name) / "concurrent.sqlite3")
        now = 1_800_000_000_000

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: store.query("day", now), range(12)))

        self.assertTrue(all(result["range"] == "day" for result in results))

    def test_day_uses_local_midnight_boundaries(self) -> None:
        zone = datetime.now().astimezone().tzinfo
        anchor = datetime(2026, 8, 19, 15, 30, tzinfo=zone)

        result = self.store.query("day", int(anchor.timestamp() * 1000))

        start = datetime.fromtimestamp(result["start_ms"] / 1000, zone)
        end = datetime.fromtimestamp(result["end_ms"] / 1000, zone)
        self.assertEqual(start, datetime(2026, 8, 19, tzinfo=zone))
        self.assertEqual(end, datetime(2026, 8, 20, tzinfo=zone))
        self.assertEqual(result["period_label"], "2026年8月19日")

    def test_week_runs_from_monday_through_sunday(self) -> None:
        zone = datetime.now().astimezone().tzinfo
        anchor = datetime(2026, 8, 19, 15, 30, tzinfo=zone)

        result = self.store.query("week", int(anchor.timestamp() * 1000))

        start = datetime.fromtimestamp(result["start_ms"] / 1000, zone)
        end = datetime.fromtimestamp(result["end_ms"] / 1000, zone)
        self.assertEqual(start, datetime(2026, 8, 17, tzinfo=zone))
        self.assertEqual(end, datetime(2026, 8, 24, tzinfo=zone))
        self.assertEqual(result["period_label"], "2026年8月17日–2026年8月23日")

    def test_month_runs_from_first_day_to_next_month(self) -> None:
        zone = datetime.now().astimezone().tzinfo
        anchor = datetime(2028, 2, 20, 12, tzinfo=zone)

        result = self.store.query("month", int(anchor.timestamp() * 1000))

        start = datetime.fromtimestamp(result["start_ms"] / 1000, zone)
        end = datetime.fromtimestamp(result["end_ms"] / 1000, zone)
        self.assertEqual(start, datetime(2028, 2, 1, tzinfo=zone))
        self.assertEqual(end, datetime(2028, 3, 1, tzinfo=zone))
        self.assertEqual((end - timedelta(milliseconds=1)).day, 29)

    def test_anchor_selects_previous_calendar_day(self) -> None:
        zone = datetime.now().astimezone().tzinfo
        now = datetime(2026, 8, 19, 15, 30, tzinfo=zone)
        previous = datetime(2026, 8, 18, 23, 59, tzinfo=zone)

        result = self.store.query(
            "day",
            int(now.timestamp() * 1000),
            int(previous.timestamp() * 1000),
        )

        start = datetime.fromtimestamp(result["start_ms"] / 1000, zone)
        self.assertEqual(start.date(), previous.date())

    def test_day_boundaries_follow_daylight_saving_time(self) -> None:
        with local_timezone("America/New_York"):
            anchor_ms = int(datetime(2026, 3, 8, 12).timestamp() * 1000)

            result = self.store.query("day", anchor_ms)

            start = datetime.fromtimestamp(result["start_ms"] / 1000)
            end = datetime.fromtimestamp(result["end_ms"] / 1000)
            self.assertEqual(start, datetime(2026, 3, 8))
            self.assertEqual(end, datetime(2026, 3, 9))
            self.assertEqual(result["end_ms"] - result["start_ms"], 23 * 60 * 60_000)

    def test_month_buckets_align_to_local_midnight(self) -> None:
        with local_timezone("Asia/Kolkata"):
            anchor_ms = int(datetime(2026, 8, 15, 12).timestamp() * 1000)
            period = self.store.query("month", anchor_ms)
            self.store.record(period["start_ms"] + 60_000, 12.0, 24.0)

            result = self.store.query("month", anchor_ms)

            self.assertEqual(result["samples"][0]["timestamp_ms"], period["start_ms"])
            self.assertEqual(result["samples"][0]["decode"], 12.0)

    def test_calendar_query_includes_start_and_excludes_end(self) -> None:
        anchor_ms = int(datetime(2026, 8, 19, 12).timestamp() * 1000)
        period = self.store.query("day", anchor_ms)
        self.store.record(period["start_ms"], 10.0, 20.0)
        self.store.record(period["end_ms"], 30.0, 40.0)

        result = self.store.query("day", anchor_ms)

        self.assertTrue(result["samples"])
        self.assertTrue(all(sample["decode"] == 10.0 for sample in result["samples"]))
        self.assertTrue(all(sample["timestamp_ms"] < period["end_ms"] for sample in result["samples"]))

    def test_rejects_unrepresentable_anchor(self) -> None:
        with self.assertRaisesRegex(ValueError, "日期范围"):
            self.store.query("day", 1_800_000_000_000, 10**30)

    def test_rejects_unknown_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "不支持"):
            self.store.query("year", 1_800_000_000_000)


if __name__ == "__main__":
    unittest.main()

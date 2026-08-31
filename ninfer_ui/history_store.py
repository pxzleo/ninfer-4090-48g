from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any


RANGES = {
    "realtime": {"window_ms": 5 * 60_000, "bucket_ms": 2_000, "label": "最近5分钟 · 2秒采样"},
    "day": {"bucket_ms": 5 * 60_000, "label": "自然日 · 均值与峰值分离"},
    "week": {"bucket_ms": 10 * 60_000, "label": "自然周 · 均值与峰值分离"},
    "month": {"bucket_ms": 2 * 60 * 60_000, "label": "自然月 · 均值与峰值分离"},
}
AGGREGATE_RETENTION_MS = 400 * 24 * 60 * 60_000
COMPLETED_REQUEST_LIMIT = 50
MAX_DETAIL_BUCKETS = 1_440
DETAIL_BUCKETS_MS = tuple(
    minutes * 60_000 for minutes in (1, 2, 5, 10, 15, 30, 60, 120, 240, 360, 720, 1_440)
)


def _calendar_range(period: str, anchor_ms: int) -> tuple[int, int, str]:
    try:
        anchor = datetime.fromtimestamp(anchor_ms / 1000)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("anchor_ms 超出可支持的日期范围") from exc
    if period == "day":
        start = datetime.combine(anchor.date(), time.min)
        end = start + timedelta(days=1)
        period_label = f"{start.year}年{start.month}月{start.day}日"
    elif period == "week":
        start_date = anchor.date() - timedelta(days=anchor.weekday())
        start = datetime.combine(start_date, time.min)
        end = start + timedelta(days=7)
        last = end - timedelta(days=1)
        period_label = (
            f"{start.year}年{start.month}月{start.day}日"
            f"–{last.year}年{last.month}月{last.day}日"
        )
    elif period == "month":
        start = datetime(anchor.year, anchor.month, 1)
        if anchor.month == 12:
            end = datetime(anchor.year + 1, 1, 1)
        else:
            end = datetime(anchor.year, anchor.month + 1, 1)
        period_label = f"{start.year}年{start.month}月"
    else:
        raise ValueError(f"不支持的日历范围: {period}")
    try:
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), period_label
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("anchor_ms 超出可支持的日期范围") from exc


def _calendar_date_range(start_value: str, end_value: str) -> tuple[int, int]:
    try:
        start_date = date.fromisoformat(start_value)
        end_date = date.fromisoformat(end_value)
    except ValueError as exc:
        raise ValueError("清理日期格式无效") from exc
    if end_date < start_date:
        raise ValueError("结束日期不能早于开始日期")
    try:
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(end_date + timedelta(days=1), time.min)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("清理日期超出可支持范围") from exc


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path
        self._schema_lock = threading.Lock()
        self._schema_ready = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        with self._schema_lock:
            if not self._schema_ready:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS throughput_raw (
                        timestamp_ms INTEGER PRIMARY KEY,
                        decode_rate REAL NOT NULL,
                        prefill_rate REAL NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS throughput_minute (
                        bucket_ms INTEGER PRIMARY KEY,
                        decode_sum REAL NOT NULL,
                        prefill_sum REAL NOT NULL,
                        sample_count INTEGER NOT NULL,
                        decode_peak REAL NOT NULL DEFAULT 0,
                        decode_peak_ms INTEGER NOT NULL DEFAULT 0,
                        prefill_peak REAL NOT NULL DEFAULT 0,
                        prefill_peak_ms INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS completed_requests (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_line TEXT NOT NULL UNIQUE,
                        event_timestamp_ms INTEGER NOT NULL DEFAULT 0,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                request_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(completed_requests)")
                }
                if "event_timestamp_ms" not in request_columns:
                    connection.execute(
                        "ALTER TABLE completed_requests ADD COLUMN "
                        "event_timestamp_ms INTEGER NOT NULL DEFAULT 0"
                    )
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(throughput_minute)")
                }
                additions = {
                    "decode_peak": "REAL NOT NULL DEFAULT 0",
                    "decode_peak_ms": "INTEGER NOT NULL DEFAULT 0",
                    "prefill_peak": "REAL NOT NULL DEFAULT 0",
                    "prefill_peak_ms": "INTEGER NOT NULL DEFAULT 0",
                }
                for name, definition in additions.items():
                    if name not in columns:
                        connection.execute(
                            f"ALTER TABLE throughput_minute ADD COLUMN {name} {definition}"
                        )
                connection.execute(
                    """
                    UPDATE throughput_minute
                    SET decode_peak = decode_sum / sample_count,
                        decode_peak_ms = bucket_ms,
                        prefill_peak = prefill_sum / sample_count,
                        prefill_peak_ms = bucket_ms
                    WHERE decode_peak_ms = 0 OR prefill_peak_ms = 0
                    """
                )
                connection.commit()
                self._schema_ready = True
        return connection

    def record_completed_requests(self, events: list[dict[str, Any]]) -> None:
        rows: list[tuple[str, int, str]] = []
        for event in reversed(events):
            if not isinstance(event, dict):
                raise ValueError("完成请求记录必须是对象")
            source_line = event.get("line")
            if not isinstance(source_line, str) or not source_line:
                raise ValueError("完成请求记录缺少原始日志")
            rows.append(
                (
                    source_line,
                    int(event.get("timestamp_ms", 0)),
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")),
                )
            )
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO completed_requests (
                    source_line, event_timestamp_ms, payload_json
                ) VALUES (?, ?, ?)
                ON CONFLICT(source_line) DO UPDATE SET
                    event_timestamp_ms = excluded.event_timestamp_ms,
                    payload_json = excluded.payload_json
                """,
                rows,
            )
            connection.execute(
                """
                DELETE FROM completed_requests
                WHERE sequence NOT IN (
                    SELECT sequence FROM completed_requests
                    ORDER BY event_timestamp_ms DESC, sequence DESC LIMIT ?
                )
                """,
                (COMPLETED_REQUEST_LIMIT,),
            )

    def recent_completed_requests(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM completed_requests
                ORDER BY event_timestamp_ms DESC, sequence DESC LIMIT ?
                """,
                (COMPLETED_REQUEST_LIMIT,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for (payload_json,) in rows:
            payload = json.loads(payload_json)
            if not isinstance(payload, dict):
                raise ValueError("完成请求数据库包含无效记录")
            events.append(payload)
        return events

    def record(self, timestamp_ms: int, decode_rate: float, prefill_rate: float) -> None:
        if timestamp_ms <= 0:
            raise ValueError("timestamp_ms 必须为正数")
        if decode_rate < 0 or prefill_rate < 0:
            raise ValueError("吞吐率不能为负数")
        minute_ms = timestamp_ms // 60_000 * 60_000
        with self._connect() as connection:
            inserted = connection.execute(
                "INSERT OR IGNORE INTO throughput_raw VALUES (?, ?, ?)",
                (timestamp_ms, decode_rate, prefill_rate),
            )
            if inserted.rowcount == 0:
                return
            connection.execute(
                """
                INSERT INTO throughput_minute (
                    bucket_ms, decode_sum, prefill_sum, sample_count,
                    decode_peak, decode_peak_ms, prefill_peak, prefill_peak_ms
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(bucket_ms) DO UPDATE SET
                    decode_sum = decode_sum + excluded.decode_sum,
                    prefill_sum = prefill_sum + excluded.prefill_sum,
                    sample_count = sample_count + 1,
                    decode_peak_ms = CASE
                        WHEN excluded.decode_peak > decode_peak
                        THEN excluded.decode_peak_ms ELSE decode_peak_ms END,
                    decode_peak = MAX(decode_peak, excluded.decode_peak),
                    prefill_peak_ms = CASE
                        WHEN excluded.prefill_peak > prefill_peak
                        THEN excluded.prefill_peak_ms ELSE prefill_peak_ms END,
                    prefill_peak = MAX(prefill_peak, excluded.prefill_peak)
                """,
                (
                    minute_ms,
                    decode_rate,
                    prefill_rate,
                    decode_rate,
                    timestamp_ms,
                    prefill_rate,
                    timestamp_ms,
                ),
            )
            connection.execute(
                "DELETE FROM throughput_raw WHERE timestamp_ms < ?",
                (timestamp_ms - RANGES["realtime"]["window_ms"],),
            )
            retention_cutoff_ms = (
                (timestamp_ms - AGGREGATE_RETENTION_MS) // 60_000 * 60_000
            )
            connection.execute(
                "DELETE FROM throughput_minute WHERE bucket_ms < ?",
                (retention_cutoff_ms,),
            )

    def clear_range(self, start_ms: int, end_ms: int) -> dict[str, int]:
        if start_ms <= 0 or end_ms <= 0:
            raise ValueError("清理时间范围必须为正数")
        if end_ms <= start_ms:
            raise ValueError("结束时间必须晚于开始时间")
        if start_ms % 60_000 or end_ms % 60_000:
            raise ValueError("清理时间范围必须按整分钟对齐")
        with self._connect() as connection:
            raw = connection.execute(
                "DELETE FROM throughput_raw WHERE timestamp_ms >= ? AND timestamp_ms < ?",
                (start_ms, end_ms),
            )
            aggregate = connection.execute(
                "DELETE FROM throughput_minute WHERE bucket_ms >= ? AND bucket_ms < ?",
                (start_ms, end_ms),
            )
        return {"raw_rows": raw.rowcount, "aggregate_rows": aggregate.rowcount}

    def clear_dates(self, start_value: str, end_value: str) -> dict[str, int]:
        start_ms, end_ms = _calendar_date_range(start_value, end_value)
        return self.clear_range(start_ms, end_ms)

    def query(
        self,
        period: str,
        now_ms: int,
        anchor_ms: int | None = None,
        detail_start_ms: int | None = None,
        detail_end_ms: int | None = None,
    ) -> dict[str, Any]:
        if period not in RANGES:
            raise ValueError(f"不支持的时间范围: {period}")
        if now_ms <= 0:
            raise ValueError("now_ms 必须为正数")
        if anchor_ms is not None and anchor_ms <= 0:
            raise ValueError("anchor_ms 必须为正数")
        config = RANGES[period]
        if period == "realtime":
            start_ms = now_ms - config["window_ms"]
            end_ms = now_ms
            period_label = "最近5分钟"
        else:
            start_ms, end_ms, period_label = _calendar_range(period, anchor_ms or now_ms)
        is_current_period = period != "realtime" and start_ms <= now_ms < end_ms
        available_end_ms = min(end_ms, now_ms) if is_current_period else end_ms
        detail_requested = detail_start_ms is not None or detail_end_ms is not None
        detail_reset = False
        if (
            detail_requested
            and anchor_ms is None
            and detail_start_ms is not None
            and detail_end_ms is not None
            and detail_end_ms <= start_ms
        ):
            detail_start_ms = None
            detail_end_ms = None
            detail_requested = False
            detail_reset = True
        if detail_requested:
            if period == "realtime":
                raise ValueError("实时范围不支持历史明细窗口")
            if detail_start_ms is None or detail_end_ms is None:
                raise ValueError("历史明细窗口必须同时提供开始和结束时间")
            if detail_start_ms < start_ms or detail_end_ms > available_end_ms:
                raise ValueError("历史明细窗口超出当前周期")
            if detail_end_ms <= detail_start_ms:
                raise ValueError("历史明细窗口结束时间必须晚于开始时间")
        with self._connect() as connection:
            if period == "realtime":
                rows = connection.execute(
                    """
                    SELECT timestamp_ms, decode_rate, prefill_rate
                    FROM throughput_raw
                    WHERE timestamp_ms >= ? AND timestamp_ms <= ?
                    ORDER BY timestamp_ms
                    """,
                    (start_ms, now_ms),
                ).fetchall()
                samples = [
                    {"timestamp_ms": row[0], "decode": row[1], "prefill": row[2]}
                    for row in rows
                ]
                overview_samples = samples
                sample_bucket_ms = config["bucket_ms"]
            else:
                overview_rows = connection.execute(
                    """
                    SELECT bucket_ms, decode_sum, prefill_sum, sample_count,
                           decode_peak, decode_peak_ms, prefill_peak, prefill_peak_ms
                    FROM throughput_minute
                    WHERE bucket_ms >= ? AND bucket_ms < ?
                    ORDER BY bucket_ms
                    """,
                    (start_ms, available_end_ms),
                ).fetchall()
                overview_samples = self._aggregate_with_peaks(
                    overview_rows, start_ms, available_end_ms, config["bucket_ms"]
                )
                if detail_requested:
                    assert detail_start_ms is not None and detail_end_ms is not None
                    sample_bucket_ms = self._detail_bucket_ms(
                        detail_end_ms - detail_start_ms
                    )
                    query_start_ms = max(start_ms, detail_start_ms // 60_000 * 60_000)
                    query_end_ms = min(
                        available_end_ms,
                        (detail_end_ms + 59_999) // 60_000 * 60_000,
                    )
                    detail_rows = connection.execute(
                        """
                        SELECT bucket_ms, decode_sum, prefill_sum, sample_count,
                               decode_peak, decode_peak_ms, prefill_peak, prefill_peak_ms
                        FROM throughput_minute
                        WHERE bucket_ms >= ? AND bucket_ms < ?
                        ORDER BY bucket_ms
                        """,
                        (query_start_ms, query_end_ms),
                    ).fetchall()
                    samples = self._aggregate_with_peaks(
                        detail_rows,
                        query_start_ms,
                        query_end_ms,
                        sample_bucket_ms,
                    )
                else:
                    samples = overview_samples
                    sample_bucket_ms = config["bucket_ms"]
        return {
            "range": period,
            "label": config["label"],
            "period_label": period_label,
            "period_anchor_ms": start_ms,
            "is_current_period": is_current_period,
            "bucket_ms": config["bucket_ms"],
            "compression": "raw" if period == "realtime" else "average_peak_envelope",
            "start_ms": start_ms,
            "end_ms": end_ms,
            "available_end_ms": available_end_ms,
            "sample_bucket_ms": sample_bucket_ms,
            "detail_start_ms": detail_start_ms,
            "detail_end_ms": detail_end_ms,
            "detail_reset": detail_reset,
            "samples": samples,
            "overview_samples": overview_samples,
        }

    @staticmethod
    def _detail_bucket_ms(duration_ms: int) -> int:
        if duration_ms <= 0:
            raise ValueError("历史明细窗口时长必须为正数")
        minimum = (duration_ms + MAX_DETAIL_BUCKETS - 1) // MAX_DETAIL_BUCKETS
        for bucket_ms in DETAIL_BUCKETS_MS:
            if bucket_ms >= minimum:
                return bucket_ms
        return DETAIL_BUCKETS_MS[-1]

    @staticmethod
    def _aggregate_with_peaks(
        rows: list[tuple[Any, ...]], start_ms: int, end_ms: int, bucket_ms: int
    ) -> list[dict[str, float | int]]:
        groups: dict[int, dict[str, float | int]] = {}
        for row in rows:
            group_start = ((int(row[0]) - start_ms) // bucket_ms) * bucket_ms + start_ms
            group = groups.setdefault(
                group_start,
                {
                    "decode_sum": 0.0,
                    "prefill_sum": 0.0,
                    "count": 0,
                    "decode_peak": 0.0,
                    "decode_peak_ms": group_start,
                    "prefill_peak": 0.0,
                    "prefill_peak_ms": group_start,
                },
            )
            group["decode_sum"] = float(group["decode_sum"]) + float(row[1])
            group["prefill_sum"] = float(group["prefill_sum"]) + float(row[2])
            group["count"] = int(group["count"]) + int(row[3])
            if float(row[4]) > float(group["decode_peak"]):
                group["decode_peak"] = float(row[4])
                group["decode_peak_ms"] = int(row[5])
            if float(row[6]) > float(group["prefill_peak"]):
                group["prefill_peak"] = float(row[6])
                group["prefill_peak_ms"] = int(row[7])

        aggregated: list[dict[str, float | int]] = []
        for group_start, group in groups.items():
            count = int(group["count"])
            if count <= 0:
                raise ValueError("历史聚合样本数必须为正数")
            decode_average = float(group["decode_sum"]) / count
            prefill_average = float(group["prefill_sum"]) / count
            group_end = min(end_ms, group_start + bucket_ms)
            decode_peak_ms = min(group_end - 1, max(group_start, int(group["decode_peak_ms"])))
            prefill_peak_ms = min(group_end - 1, max(group_start, int(group["prefill_peak_ms"])))
            aggregated.append(
                {
                    "timestamp_ms": group_start,
                    "bucket_end_ms": group_end,
                    "decode": decode_average,
                    "prefill": prefill_average,
                    "decode_peak": float(group["decode_peak"]),
                    "decode_peak_ms": decode_peak_ms,
                    "prefill_peak": float(group["prefill_peak"]),
                    "prefill_peak_ms": prefill_peak_ms,
                }
            )
        return aggregated

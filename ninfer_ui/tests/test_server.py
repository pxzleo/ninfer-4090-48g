import sys
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch


UI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI_ROOT))

import server as server_module  # noqa: E402
from server import host_name, lan_api_url, latest_throughput, request_events  # noqa: E402


class RequestEventsTest(unittest.TestCase):
    def setUp(self) -> None:
        server_module.REQUEST_BACKFILL_COMPLETE = False

    @patch.object(server_module, "LAN_API_OVERRIDE", "http://192.168.100.149:8080/v1")
    def test_lan_api_override_is_used_verbatim(self) -> None:
        self.assertEqual(lan_api_url(), "http://192.168.100.149:8080/v1")

    @patch.object(server_module, "LAN_API_OVERRIDE", "not-an-address")
    def test_lan_api_override_rejects_invalid_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "有效"):
            lan_api_url()

    def test_slot_kv_sum_reconciles_snapshot_total(self) -> None:
        metrics = {
            "ninfer:kv_cache_used_tokens": 999.0,
            "ninfer:kv_cache_capacity_tokens": 524288.0,
        }
        slots = [
            {"id": 0, "is_processing": True, "n_kv_tokens": 194112},
            {"id": 1, "is_processing": False, "n_kv_tokens": 237120},
        ]

        server_module.reconcile_slot_kv_usage(metrics, slots)

        self.assertEqual(metrics["ninfer:kv_cache_used_tokens"], 431232.0)

    def test_old_slots_keep_pool_total(self) -> None:
        metrics = {"ninfer:kv_cache_used_tokens": 431232.0}

        server_module.reconcile_slot_kv_usage(
            metrics, [{"id": 0, "n_prompt_tokens": 193848}]
        )

        self.assertEqual(metrics["ninfer:kv_cache_used_tokens"], 431232.0)

    def test_slot_kv_sum_rejects_invalid_values(self) -> None:
        metrics = {"ninfer:kv_cache_capacity_tokens": 524288.0}
        with self.assertRaisesRegex(ValueError, "无效"):
            server_module.reconcile_slot_kv_usage(
                metrics, [{"id": 0, "n_kv_tokens": -64}]
            )

    def test_slot_kv_sum_rejects_capacity_overflow(self) -> None:
        metrics = {"ninfer:kv_cache_capacity_tokens": 64.0}
        with self.assertRaisesRegex(ValueError, "超过"):
            server_module.reconcile_slot_kv_usage(
                metrics, [{"id": 0, "n_kv_tokens": 128}]
            )

    def test_parses_nanosecond_docker_timestamp(self) -> None:
        line = (
            "2026-08-19T08:07:57.371626300Z [info] throughput interval=2.000s "
            "prefill=1024.0tok/s decode=66.5tok/s running=1 prefilling=1 "
            "decode_ready=0 waiting=0 avg_decode_batch=n/a"
        )

        throughput = latest_throughput([line])

        self.assertIsNotNone(throughput)
        self.assertEqual(throughput["timestamp_ms"], 1787126877371)

    def test_parses_cache_tokens_and_hit_rate(self) -> None:
        line = (
            "2026-08-19T08:07:57.371626300Z [req 9] done finish=tool_calls "
            "tool_calls=3 prompt=49020 gen=5370 "
            "cache=43358 reuse=append_frontier ttft=8980ms prefill=1563.4tok/s "
            "decode=79.3tok/s wall=76.84s speculative=mtp 2.14tok/round (38.0%)"
        )

        events = request_events([line])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["cache_tokens"], 43358)
        self.assertAlmostEqual(events[0]["cache_hit_rate"], 88.4496, places=3)
        self.assertEqual(events[0]["timestamp_ms"], 1787126877371)

    def test_request_event_parser_accepts_fifty_rows(self) -> None:
        lines = [
            f"[req {request_id}] done finish=stop_token prompt=10 gen=2 cache=0 "
            "reuse=full_reset ttft=10ms prefill=10.0tok/s decode=20.0tok/s "
            "wall=1.00s speculative=mtp 2.00tok/round (50.0%)"
            for request_id in range(1, 56)
        ]

        events = request_events(lines, limit=50)

        self.assertEqual(len(events), 50)
        self.assertEqual(events[0]["id"], 55)
        self.assertEqual(events[-1]["id"], 6)

    @patch.object(server_module, "gpu_state", return_value={"available": True})
    @patch.object(server_module, "container_state", return_value={"running": True})
    @patch.object(server_module, "fetch_text", return_value="")
    @patch.object(
        server_module,
        "fetch_json",
        side_effect=[{"status": "ok"}, [], {"data": []}],
    )
    @patch.object(server_module, "docker_logs", side_effect=RuntimeError("unavailable"))
    @patch.object(server_module, "HISTORY")
    def test_snapshot_keeps_persisted_requests_when_logs_are_unavailable(
        self, history, _logs, _fetch_json, _fetch_text, _container, _gpu
    ) -> None:
        history.recent_completed_requests.return_value = [{"id": 42}]

        snapshot = server_module.collect_snapshot()

        self.assertEqual(snapshot["recent_requests"], [{"id": 42}])
        self.assertTrue(any("Docker logs" in error for error in snapshot["errors"]))

    @patch.object(server_module, "gpu_state", return_value={"available": True})
    @patch.object(server_module, "container_state", return_value={"running": True})
    @patch.object(server_module, "fetch_text", return_value="")
    @patch.object(
        server_module,
        "fetch_json",
        side_effect=[{"status": "ok"}, [], {"data": []}],
    )
    @patch.object(
        server_module,
        "docker_logs",
        return_value=[
            "2026-08-19T08:07:57.000000000Z [info] throughput interval=2.000s "
            "prefill=0.0tok/s decode=15.5tok/s running=0 prefilling=0 "
            "decode_ready=0 waiting=0 avg_decode_batch=1.00"
        ],
    )
    @patch.object(server_module.time, "time", return_value=1787126887.0)
    def test_snapshot_discards_stale_throughput(
        self, _time, _logs, _fetch_json, _fetch_text, _container, _gpu
    ) -> None:
        snapshot = server_module.collect_snapshot()

        self.assertIsNone(snapshot["throughput"])

    @patch.object(server_module, "gpu_state", return_value={"available": True})
    @patch.object(server_module, "container_state", return_value={"running": True})
    @patch.object(server_module, "fetch_text", return_value="")
    @patch.object(
        server_module,
        "fetch_json",
        side_effect=[{"status": "ok"}, [], {"data": []}],
    )
    @patch.object(
        server_module,
        "docker_logs",
        return_value=[
            "2026-08-19T08:07:57.000000000Z [info] throughput interval=2.000s "
            "prefill=0.0tok/s decode=15.5tok/s running=0 prefilling=0 "
            "decode_ready=0 waiting=0 avg_decode_batch=1.00"
        ],
    )
    @patch.object(
        server_module.time, "time", side_effect=[1787126881.0, 1787126887.0]
    )
    def test_snapshot_uses_collection_end_time_for_staleness(
        self, _time, _logs, _fetch_json, _fetch_text, _container, _gpu
    ) -> None:
        snapshot = server_module.collect_snapshot()

        self.assertEqual(snapshot["timestamp_ms"], 1787126887000)
        self.assertIsNone(snapshot["throughput"])

    def test_throughput_expires_after_two_and_a_half_intervals(self) -> None:
        throughput = {"timestamp_ms": 10_000, "interval_seconds": 2.0}

        self.assertIs(
            server_module.current_throughput(throughput, 15_000), throughput
        )
        self.assertIsNone(server_module.current_throughput(throughput, 15_001))
        self.assertIsNone(server_module.current_throughput(throughput, 4_999))


class ServiceControlTest(unittest.TestCase):
    def test_host_name_accepts_ipv4_and_ipv6_loopback(self) -> None:
        self.assertEqual(host_name("127.0.0.1:8081"), "127.0.0.1")
        self.assertEqual(host_name("[::1]:8081"), "::1")

    @patch.object(server_module, "fetch_json", return_value={"status": "ok"})
    @patch.object(
        server_module,
        "container_state",
        return_value={"available": True, "running": False},
    )
    @patch.object(server_module, "docker_command")
    def test_start_uses_compose_up_and_waits_for_health(
        self, docker, _state, _fetch
    ) -> None:
        docker.return_value = CompletedProcess([], 0, "started", "")

        result = server_module.start_ninfer()

        args = docker.call_args.args[0]
        self.assertEqual(args[-3:], ["up", "-d", server_module.SERVICE_NAME])
        self.assertEqual(result["health"], "ok")

    @patch.object(
        server_module,
        "container_state",
        side_effect=[
            {"available": True, "running": True},
            {"available": True, "running": False},
        ],
    )
    @patch.object(server_module, "docker_command")
    def test_stop_uses_compose_stop_and_verifies_state(self, docker, _state) -> None:
        docker.return_value = CompletedProcess([], 0, "stopped", "")

        result = server_module.stop_ninfer()

        args = docker.call_args.args[0]
        self.assertEqual(args[-2:], ["stop", server_module.SERVICE_NAME])
        self.assertFalse(result["running"])

    @patch.object(
        server_module,
        "container_state",
        return_value={"available": True, "running": True},
    )
    def test_start_rejects_already_running_container(self, _state) -> None:
        with self.assertRaisesRegex(server_module.UiError, "已经在运行"):
            server_module.start_ninfer()

    @patch.object(
        server_module,
        "container_state",
        return_value={"available": True, "running": False},
    )
    def test_stop_rejects_already_stopped_container(self, _state) -> None:
        with self.assertRaisesRegex(server_module.UiError, "已经停止"):
            server_module.stop_ninfer()


if __name__ == "__main__":
    unittest.main()

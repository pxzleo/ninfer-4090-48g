from __future__ import annotations

import socket
import threading

from tools.bench.run_prefill_decode_balance import (
    DEFAULT_PROFILE,
    StreamClient,
    calibrate_prompt,
    choose_overlap_end,
    has_generated_delta,
    interval_metrics,
    make_server_command,
    profile_reservations,
    prompt_reservations,
    reset_summary_state,
    validate_chunks,
)


def test_sampled_profile_preserves_recent_bimodal_shape() -> None:
    assert DEFAULT_PROFILE.anchor_prompt_tokens == (109_500, 109_500, 8_000)
    assert DEFAULT_PROFILE.interferer_prompt_tokens == 109_500
    assert DEFAULT_PROFILE.requested_output_tokens == 65_536
    assert max(profile_reservations(DEFAULT_PROFILE)) <= 600_000


def test_chunks_are_unique_aligned_and_keep_requested_order() -> None:
    assert validate_chunks([1024, 256, 128]) == (1024, 256, 128)


def test_server_command_changes_only_the_selected_prefill_chunk(tmp_path) -> None:
    command = make_server_command(
        serve=tmp_path / "ninfer-serve",
        artifact=tmp_path / "model.ninfer",
        server_log=tmp_path / "server.jsonl",
        model_id="qwen3.8-27b",
        port=18080,
        device=0,
        chunk=1024,
        chunk_when_decoding=256,
        profile=DEFAULT_PROFILE,
    )
    assert command[command.index("--prefill-chunk") + 1] == "1024"
    assert command[command.index("--prefill-chunk-when-decoding") + 1] == "256"
    assert command[command.index("--max-concurrency") + 1] == "4"
    assert command[command.index("--kv-capacity") + 1] == "600000"
    assert "--no-prefix-reuse" in command


def test_interval_metrics_use_raw_counters_and_phase_window() -> None:
    events = [
        {
            "timestamp_unix_ms": 2_100,
            "interval_seconds": 1.0,
            "tokens": {"computed_prefill": 900, "committed_decode": 999},
            "scheduler": {"prefilling": 1, "decode_ready": 3},
            "decode_batch": {"rounds": 1, "row_rounds": 3},
        },
        {
            "timestamp_unix_ms": 1_500,
            "interval_seconds": 1.0,
            "tokens": {"computed_prefill": 0, "committed_decode": 120},
            "scheduler": {"prefilling": 0, "decode_ready": 3},
            "decode_batch": {"rounds": 10, "row_rounds": 30},
        },
        {
            "timestamp_unix_ms": 2_500,
            "interval_seconds": 1.0,
            "tokens": {"computed_prefill": 900, "committed_decode": 12},
            "scheduler": {"prefilling": 1, "decode_ready": 3},
            "decode_batch": {"rounds": 1, "row_rounds": 3},
        },
        {
            "timestamp_unix_ms": 3_500,
            "interval_seconds": 1.0,
            "tokens": {"computed_prefill": 0, "committed_decode": 999},
            "scheduler": {"prefilling": 0, "decode_ready": 3},
            "decode_batch": {"rounds": 1, "row_rounds": 3},
        },
    ]
    baseline = interval_metrics(events, 0, 2_000, prefill=False, anchors=3)
    overlap = interval_metrics(events, 1_500, 3_000, prefill=True, anchors=3)
    assert baseline["decode_tokens_per_second"] == 120.0
    assert baseline["average_decode_batch"] == 3.0
    assert overlap["decode_tokens_per_second"] == 12.0
    assert overlap["prefill_tokens_per_second"] == 900.0


def test_interval_metrics_reject_mixed_decode_membership() -> None:
    events = [{
        "timestamp_unix_ms": 2_500,
        "interval_seconds": 1.0,
        "tokens": {"computed_prefill": 900, "committed_decode": 12},
        "scheduler": {"prefilling": 1, "decode_ready": 4},
        "decode_batch": {"rounds": 1, "row_rounds": 4},
    }]
    try:
        interval_metrics(events, 1_000, 3_000, prefill=True, anchors=3)
    except Exception as exc:
        assert "no complete overlap" in str(exc)
    else:
        raise AssertionError("mixed decode membership must be rejected")


def test_generated_delta_ignores_role_metadata() -> None:
    assert not has_generated_delta({"choices": [{"delta": {"role": "assistant"}}]})
    assert has_generated_delta({"choices": [{"delta": {"content": "token"}}]})
    assert has_generated_delta({"choices": [{"delta": {"reasoning_content": "thought"}}]})


def test_prompt_reservations_reject_capacity_overflow_shape() -> None:
    main, backend = prompt_reservations([110_000, 110_000, 8_000, 110_000], 65_536)
    assert main > 600_000
    assert backend > 600_000


def test_reset_summary_state_removes_only_runner_status_files(tmp_path) -> None:
    names = ("summary.json", "summary.csv", "summary.md", "partial_summary.json")
    for name in names:
        (tmp_path / name).write_text("old", encoding="utf-8")
    point = tmp_path / "point.json"
    point.write_text("keep", encoding="utf-8")
    reset_summary_state(tmp_path)
    assert all(not (tmp_path / name).exists() for name in names)
    assert point.read_text(encoding="utf-8") == "keep"


def test_stream_client_stop_closes_response_socket() -> None:
    owned, reader = socket.socketpair()
    client = StreamClient(18080, {}, "socket-test")
    client.socket = owned
    client.thread = threading.Thread(target=lambda: reader.recv(1))
    client.thread.start()
    try:
        client.stop()
        assert not client.thread.is_alive()
    finally:
        reader.close()


def test_overlap_window_ends_before_decode_membership_changes() -> None:
    assert choose_overlap_end(1_000, 9_000, [0, 6_000, 10_000], 40.0) == (
        6_000,
        "anchor_finished",
    )
    assert choose_overlap_end(1_000, 9_000, [0, 10_000], 40.0) == (
        9_000,
        "interferer_first_output",
    )
    assert choose_overlap_end(1_000, 90_000, [0, 100_000], 40.0) == (
        41_000,
        "measurement_limit",
    )


def test_prompt_calibration_uses_monotonic_counter() -> None:
    text, count = calibrate_prompt(100, "prefix", lambda value: len(value) // 10, tolerance=8)
    assert abs(count - 100) <= 8
    assert text.startswith("prefix")

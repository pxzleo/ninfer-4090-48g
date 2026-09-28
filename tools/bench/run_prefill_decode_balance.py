#!/usr/bin/env python3
"""Measure decode service retained while one long prompt is being prefetched.

The workload intentionally mirrors the sampled local serving shape without retaining any user
content: two long-context decode streams, one short-context decode stream, then one long prefill.
Every prefill-chunk point starts a fresh server and changes only that startup option.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import http.client
import json
import math
import os
import shlex
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.bench import run_serve_corpus as corpus  # noqa: E402
from tools.bench.run_serve_concurrency import load_server_events  # noqa: E402


STATS_INTERVAL_MS = 1000
PENDING_TIMEOUT_MS = 24 * 60 * 60 * 1000
POINT_ARTIFACT_TYPE = "ninfer_prefill_decode_balance_point"
SUMMARY_ARTIFACT_TYPE = "ninfer_prefill_decode_balance_summary"
SCHEMA_VERSION = 1
FILLER = (
    " GPU inference services schedule bounded prompt ingestion beside batched token generation."
    " This deterministic sentence is repeated only to create a requested tokenizer length."
)
KV_PAGE_TOKENS = 64
MTP_DRAFT_WINDOW = 3
KV_CAPACITY_TOKENS = 600_000
ANCHOR_INSTRUCTION = (
    "Read the benchmark context, then emit an indefinitely long sequence of numbered, concise "
    "engineering observations. Do not summarize, conclude, or stop until the output limit.\n\n"
)
INTERFERER_INSTRUCTION = (
    "Read the complete benchmark context, then return one short sentence confirming completion.\n\n"
)


@dataclasses.dataclass(frozen=True)
class WorkloadProfile:
    anchor_prompt_tokens: tuple[int, ...]
    interferer_prompt_tokens: int
    requested_output_tokens: int
    baseline_seconds: float = 8.0
    overlap_seconds: float = 40.0
    post_seconds: float = 5.0

    @property
    def concurrency(self) -> int:
        return len(self.anchor_prompt_tokens) + 1


DEFAULT_PROFILE = WorkloadProfile(
    anchor_prompt_tokens=(109_500, 109_500, 8_000),
    interferer_prompt_tokens=109_500,
    requested_output_tokens=65_536,
)


class StreamClient:
    def __init__(self, port: int, payload: dict[str, Any], name: str) -> None:
        self.port = port
        self.payload = payload
        self.name = name
        self.connection: http.client.HTTPConnection | None = None
        self.socket: socket.socket | None = None
        self.thread = threading.Thread(target=self._run, name=name)
        self.started = threading.Event()
        self.first_event = threading.Event()
        self.finished = threading.Event()
        self.stopping = threading.Event()
        self.error: Exception | None = None
        self.started_at = 0.0
        self.first_event_at = 0.0
        self.finished_wall_ms = 0
        self.events = 0

    def start(self) -> None:
        self.thread.start()
        if not self.started.wait(timeout=10.0):
            raise corpus.CampaignError(f"{self.name} did not start")
        if self.error is not None:
            raise corpus.CampaignError(f"{self.name} failed to start: {self.error}")

    def _run(self) -> None:
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.port, timeout=corpus.REQUEST_TIMEOUT_SECONDS
        )
        self.connection = connection
        body = json.dumps(self.payload, ensure_ascii=False, separators=(",", ":")).encode()
        try:
            connection.connect()
            self.started_at = time.monotonic()
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=body,
                headers={
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "Connection": "close",
                    "X-NInfer-Client": "prefill-decode-balance",
                    "X-NInfer-Agent": self.name,
                },
            )
            self.socket = connection.sock
            self.started.set()
            response = connection.getresponse()
            if response.status != 200:
                detail = response.read().decode("utf-8", errors="replace")
                raise corpus.CampaignError(
                    f"{self.name} received HTTP {response.status}: {detail}"
                )
            while True:
                line = response.readline()
                if not line:
                    break
                if not line.startswith(b"data: "):
                    continue
                data = line[6:].strip()
                if data == b"[DONE]":
                    break
                event = json.loads(data)
                self.events += 1
                if has_generated_delta(event) and not self.first_event.is_set():
                    self.first_event_at = time.monotonic()
                    self.first_event.set()
        except Exception as exc:
            if not self.stopping.is_set():
                self.error = exc
            self.started.set()
        finally:
            self.finished_wall_ms = int(time.time() * 1000)
            connection.close()
            self.finished.set()

    def stop(self) -> None:
        self.stopping.set()
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        if self.connection is not None:
            self.connection.close()
        self.thread.join(timeout=10.0)
        if self.thread.is_alive():
            raise corpus.CampaignError(f"{self.name} did not stop after its socket was closed")


def has_generated_delta(event: Any) -> bool:
    """Return true only for an SSE chunk carrying generated model output."""
    try:
        delta = event["choices"][0]["delta"]
    except (KeyError, IndexError, TypeError):
        return False
    if not isinstance(delta, dict):
        return False
    for name in ("content", "reasoning_content", "reasoning"):
        value = delta.get(name)
        if isinstance(value, str) and value:
            return True
    return bool(delta.get("tool_calls"))


def validate_chunks(values: Sequence[int]) -> tuple[int, ...]:
    chunks = tuple(values)
    if not chunks:
        raise corpus.CampaignError("at least one --prefill-chunk is required")
    if len(chunks) != len(set(chunks)):
        raise corpus.CampaignError("duplicate --prefill-chunk value")
    if any(chunk <= 0 or chunk % 128 != 0 for chunk in chunks):
        raise corpus.CampaignError("prefill chunks must be positive multiples of 128")
    return chunks


def prompt_reservations(
    prompts: Sequence[int], requested_output_tokens: int
) -> tuple[int, int]:
    def aligned(tokens: int) -> int:
        return math.ceil(tokens / KV_PAGE_TOKENS) * KV_PAGE_TOKENS

    main = sum(
        aligned(prompt + requested_output_tokens - 1) for prompt in prompts
    )
    backend = sum(
        aligned(prompt + requested_output_tokens - 1 + MTP_DRAFT_WINDOW - 1)
        for prompt in prompts
    )
    return main, backend


def profile_reservations(profile: WorkloadProfile) -> tuple[int, int]:
    return prompt_reservations(
        (*profile.anchor_prompt_tokens, profile.interferer_prompt_tokens),
        profile.requested_output_tokens,
    )


def validate_server_start(
    event: dict[str, Any],
    profile: WorkloadProfile,
    model_id: str,
    device: int,
    chunk: int,
    chunk_when_decoding: int,
) -> tuple[str, str, str]:
    corpus.require_server_log_identity(event, "server_start")
    engine = event.get("engine", {})
    expected = {
        "device": device,
        "max_context": 262_144,
        "kv_capacity_mode": "explicit",
        "kv_capacity": KV_CAPACITY_TOKENS,
        "max_concurrency": profile.concurrency,
        "max_pending_requests": 2,
        "pending_timeout_ms": PENDING_TIMEOUT_MS,
        "prefill_chunk": chunk,
        "prefill_chunk_when_decoding": chunk_when_decoding,
        "log_stats_interval_ms": STATS_INTERVAL_MS,
        "kv_cache": "int8-group64",
        "cuda_graph": True,
        "prefix_reuse": False,
        "speculative_backend": "mtp",
        "speculative_draft_window": MTP_DRAFT_WINDOW,
        "proposal_head": "optimized",
    }
    actual = {name: engine.get(name) for name in expected}
    if actual != expected:
        raise corpus.CampaignError(f"server_start Engine configuration mismatch: {actual!r}")
    if event.get("sampling_defaults", {}).get("greedy") is not True:
        raise corpus.CampaignError("server_start sampling mode is not greedy")
    if event.get("server", {}).get("public_model_id") != model_id:
        raise corpus.CampaignError("server public model id does not match the point")
    artifact = event.get("artifact", {})
    server_instance_id = event.get("server_instance_id")
    weights_id = artifact.get("weights_id")
    target = artifact.get("target")
    if not isinstance(server_instance_id, str) or not server_instance_id:
        raise corpus.CampaignError("server_start has no server_instance_id")
    if not isinstance(weights_id, str) or not weights_id:
        raise corpus.CampaignError("server_start has no canonical weights_id")
    if target != "qwen3_8_27b":
        raise corpus.CampaignError(f"loaded artifact target is not qwen3_8_27b: {target!r}")
    return server_instance_id, weights_id, target


def require_clients_live(clients: Sequence[StreamClient], phase: str) -> None:
    for client in clients:
        if client.error is not None:
            raise corpus.CampaignError(f"{client.name} failed during {phase}: {client.error}")
        if client.finished.is_set():
            raise corpus.CampaignError(f"{client.name} finished during {phase}")


def choose_overlap_end(
    overlap_start_ms: int,
    interferer_first_output_ms: int,
    anchor_finished_ms: Sequence[int],
    measurement_seconds: float,
) -> tuple[int, str]:
    candidates = [(interferer_first_output_ms, "interferer_first_output")]
    candidates.extend(
        (timestamp, "anchor_finished")
        for timestamp in anchor_finished_ms
        if timestamp > overlap_start_ms
    )
    candidates.append(
        (overlap_start_ms + int(measurement_seconds * 1000), "measurement_limit")
    )
    return min(candidates, key=lambda candidate: candidate[0])


def make_server_command(
    serve: Path,
    artifact: Path,
    server_log: Path,
    model_id: str,
    port: int,
    device: int,
    chunk: int,
    chunk_when_decoding: int,
    profile: WorkloadProfile,
) -> list[str]:
    main_reservation, backend_reservation = profile_reservations(profile)
    if max(main_reservation, backend_reservation) > KV_CAPACITY_TOKENS:
        raise corpus.CampaignError(
            "synthetic workload reservation exceeds the configured shared KV capacity"
        )
    return [
        str(serve),
        str(artifact),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--model-id",
        model_id,
        "--max-context",
        "262144",
        "--kv-capacity",
        str(KV_CAPACITY_TOKENS),
        "--max-concurrency",
        str(profile.concurrency),
        "--max-pending-requests",
        "2",
        "--pending-timeout-ms",
        str(PENDING_TIMEOUT_MS),
        "--prefill-chunk",
        str(chunk),
        "--prefill-chunk-when-decoding",
        str(chunk_when_decoding),
        "--log-stats-interval-ms",
        str(STATS_INTERVAL_MS),
        "--device",
        str(device),
        "--request-log-jsonl",
        str(server_log),
        "--kv-dtype",
        "int8",
        "--spec",
        "mtp",
        "--draft-tokens",
        "3",
        "--lm-head-draft",
        "--no-prefix-reuse",
        "--no-thinking",
        "--greedy",
    ]


def post_json_path(port: int, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30.0)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    try:
        connection.request(
            "POST",
            path,
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        response = connection.getresponse()
        content = response.read()
    finally:
        connection.close()
    if response.status != 200:
        raise corpus.CampaignError(
            f"{path} returned HTTP {response.status}: {content.decode(errors='replace')}"
        )
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise corpus.CampaignError(f"{path} did not return an object")
    return parsed


def prompt_count(port: int, model_id: str, text: str) -> int:
    result = post_json_path(
        port,
        "/v1/responses/input_tokens",
        {"model": model_id, "input": text},
    )
    try:
        return int(result["input_tokens"])
    except (KeyError, TypeError, ValueError) as exc:
        raise corpus.CampaignError(f"invalid input-token response: {result!r}") from exc


def calibrate_prompt(
    target: int,
    instruction: str,
    counter: Callable[[str], int],
    tolerance: int = 64,
) -> tuple[str, int]:
    if target <= 0:
        raise corpus.CampaignError("prompt target must be positive")
    low, high = 0, 1
    while counter(instruction + FILLER * high) < target and high < target * 2:
        low, high = high, high * 2
    best_text = instruction
    best_count = counter(best_text)
    while low <= high:
        middle = (low + high) // 2
        text = instruction + FILLER * middle
        count = counter(text)
        if abs(count - target) < abs(best_count - target):
            best_text, best_count = text, count
        if count < target:
            low = middle + 1
        elif count > target:
            high = middle - 1
        else:
            break
    if abs(best_count - target) > tolerance:
        raise corpus.CampaignError(
            f"could not calibrate prompt target {target}; closest count is {best_count}"
        )
    return best_text, best_count


def get_slots(port: int) -> list[dict[str, Any]]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        connection.request("GET", "/slots", headers={"Connection": "close"})
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()
    if response.status != 200:
        raise corpus.CampaignError(f"/slots returned HTTP {response.status}")
    parsed = json.loads(body)
    if not isinstance(parsed, list):
        raise corpus.CampaignError("/slots did not return an array")
    return parsed


def wait_slots(
    port: int, predicate: Callable[[list[dict[str, Any]]], bool], description: str, timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        slots = get_slots(port)
        if predicate(slots):
            return
        if time.monotonic() >= deadline:
            raise corpus.CampaignError(f"timed out waiting for {description}: {slots!r}")
        time.sleep(0.2)


def stream_payload(model_id: str, text: str, output_tokens: int) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [{"role": "user", "content": text}],
        "max_completion_tokens": output_tokens,
        "stream": True,
        "enable_thinking": False,
        "temperature": 0,
        "seed": 20260901,
    }


def interval_metrics(
    events: Sequence[dict[str, Any]],
    start_ms: int,
    end_ms: int,
    *,
    prefill: bool,
    anchors: int,
) -> dict[str, int | float]:
    selected: list[dict[str, Any]] = []
    for event in events:
        if event.get("event") not in (None, "throughput"):
            continue
        timestamp = int(event.get("timestamp_unix_ms", -1))
        interval_seconds = float(event.get("interval_seconds", 0.0))
        interval_start = timestamp - int(interval_seconds * 1000)
        if interval_start < start_ms or timestamp > end_ms:
            continue
        scheduler = event.get("scheduler", {})
        if int(scheduler.get("prefilling", -1)) != int(prefill):
            continue
        if int(scheduler.get("decode_ready", -1)) < anchors:
            continue
        tokens = event.get("tokens", {})
        computed_prefill = int(tokens.get("computed_prefill", -1))
        decode_batch = event.get("decode_batch", {})
        rounds = int(decode_batch.get("rounds", 0))
        row_rounds = int(decode_batch.get("row_rounds", -1))
        if rounds <= 0 or row_rounds != anchors * rounds:
            continue
        if prefill != (computed_prefill > 0):
            continue
        selected.append(event)
    if not selected:
        raise corpus.CampaignError(
            f"no complete {'overlap' if prefill else 'decode-only'} throughput interval"
        )
    seconds = sum(float(event["interval_seconds"]) for event in selected)
    decode = sum(int(event["tokens"]["committed_decode"]) for event in selected)
    computed_prefill = sum(int(event["tokens"]["computed_prefill"]) for event in selected)
    rounds = sum(int(event["decode_batch"]["rounds"]) for event in selected)
    row_rounds = sum(int(event["decode_batch"]["row_rounds"]) for event in selected)
    if seconds <= 0:
        raise corpus.CampaignError("selected throughput intervals have no duration")
    return {
        "intervals": len(selected),
        "seconds": seconds,
        "decode_tokens": decode,
        "computed_prefill_tokens": computed_prefill,
        "decode_tokens_per_second": decode / seconds,
        "prefill_tokens_per_second": computed_prefill / seconds,
        "average_decode_batch": row_rounds / rounds if rounds else 0.0,
    }


def run_point(
    serve: Path,
    artifact: Path,
    output_dir: Path,
    model_id: str,
    port: int,
    device: int,
    chunk: int,
    chunk_when_decoding: int,
    profile: WorkloadProfile,
) -> dict[str, Any]:
    point_name = f"chunk_{chunk}_decode_{chunk_when_decoding}"
    server_log = output_dir / "server" / f"{point_name}.jsonl"
    command = make_server_command(
        serve,
        artifact,
        server_log,
        model_id,
        port,
        device,
        chunk,
        chunk_when_decoding,
        profile,
    )
    anchors: list[StreamClient] = []
    owned_clients: list[StreamClient] = []
    interferer: StreamClient | None = None
    print(
        f"start prefill_chunk={chunk} prefill_chunk_when_decoding={chunk_when_decoding}",
        flush=True,
    )
    with corpus.RunningServer(command, "127.0.0.1", port, server_log) as server:
        server_start = server.wait_until_ready()
        server_instance_id, weights_id, artifact_target = validate_server_start(
            server_start, profile, model_id, device, chunk, chunk_when_decoding
        )
        counter = lambda text: prompt_count(port, model_id, text)
        prompt_cache: dict[tuple[str, int], tuple[str, int]] = {}
        for prompt_target in set(profile.anchor_prompt_tokens):
            prompt_cache[("anchor", prompt_target)] = calibrate_prompt(
                prompt_target, ANCHOR_INSTRUCTION, counter
            )
        prompt_cache[("interferer", profile.interferer_prompt_tokens)] = calibrate_prompt(
            profile.interferer_prompt_tokens, INTERFERER_INSTRUCTION, counter
        )
        actual_prompts = [
            prompt_cache[("anchor", target_tokens)][1]
            for target_tokens in profile.anchor_prompt_tokens
        ]
        actual_prompts.append(
            prompt_cache[("interferer", profile.interferer_prompt_tokens)][1]
        )
        actual_reservations = prompt_reservations(
            actual_prompts, profile.requested_output_tokens
        )
        if max(actual_reservations) > KV_CAPACITY_TOKENS:
            raise corpus.CampaignError(
                "calibrated workload reservation exceeds the configured shared KV capacity: "
                f"main={actual_reservations[0]} backend={actual_reservations[1]}"
            )
        try:
            for index, prompt_target in enumerate(profile.anchor_prompt_tokens):
                text, _ = prompt_cache[("anchor", prompt_target)]
                client = StreamClient(
                    port,
                    stream_payload(model_id, text, profile.requested_output_tokens),
                    f"anchor-{index}",
                )
                owned_clients.append(client)
                client.start()
                anchors.append(client)
                expected_active = index + 1
                wait_slots(
                    port,
                    lambda slots, expected=expected_active: sum(
                        bool(slot.get("is_processing")) for slot in slots
                    )
                    >= expected,
                    f"anchor {index} to enter an active slot",
                    900.0,
                )
                require_clients_live(anchors, f"ordered anchor admission {index}")
            anchor_count = len(anchors)
            wait_slots(
                port,
                lambda slots: sum(slot.get("state") == "decode" for slot in slots) >= anchor_count,
                "all anchor requests to enter decode",
                900.0,
            )
            if any(anchor.finished.is_set() for anchor in anchors):
                raise corpus.CampaignError("an anchor request finished before overlap measurement")
            require_clients_live(anchors, "baseline")
            baseline_start_ms = int(time.time() * 1000)
            time.sleep(profile.baseline_seconds)
            baseline_end_ms = int(time.time() * 1000)
            require_clients_live(anchors, "baseline")

            text, interferer_count = prompt_cache[
                ("interferer", profile.interferer_prompt_tokens)
            ]
            interferer = StreamClient(
                port,
                stream_payload(model_id, text, profile.requested_output_tokens),
                "interferer",
            )
            owned_clients.append(interferer)
            interferer.start()
            wait_slots(
                port,
                lambda slots: any(slot.get("state") == "prefill" for slot in slots),
                "interferer prefill to start",
                120.0,
            )
            overlap_start_ms = int(time.time() * 1000)
            if not interferer.first_event.wait(timeout=900.0):
                raise corpus.CampaignError("interferer did not reach first output event")
            interferer_first_output_ms = int(time.time() * 1000)
            overlap_end_ms, overlap_end_reason = choose_overlap_end(
                overlap_start_ms,
                interferer_first_output_ms,
                [anchor.finished_wall_ms for anchor in anchors],
                profile.overlap_seconds,
            )
            for anchor in anchors:
                if anchor.error is not None:
                    raise corpus.CampaignError(
                        f"{anchor.name} failed during overlap: {anchor.error}"
                    )
            if interferer.error is not None:
                raise corpus.CampaignError(f"interferer failed during overlap: {interferer.error}")
            time.sleep(profile.post_seconds)
        finally:
            active_error = sys.exc_info()[1]
            cleanup_errors: list[str] = []
            for client in reversed(owned_clients):
                try:
                    client.stop()
                except Exception as exc:
                    cleanup_errors.append(f"{client.name}: {exc}")
            if cleanup_errors:
                detail = "; ".join(cleanup_errors)
                if active_error is None:
                    raise corpus.CampaignError(f"client cleanup failed: {detail}")
                print(f"warning: client cleanup also failed: {detail}", file=sys.stderr)

    events = load_server_events(server_log, server_instance_id)
    throughput = [event for event in events if event.get("event") == "throughput"]
    baseline = interval_metrics(
        throughput,
        baseline_start_ms,
        baseline_end_ms,
        prefill=False,
        anchors=len(anchors),
    )
    overlap = interval_metrics(
        throughput,
        overlap_start_ms,
        overlap_end_ms,
        prefill=True,
        anchors=len(anchors),
    )
    baseline_decode = float(baseline["decode_tokens_per_second"])
    overlap_decode = float(overlap["decode_tokens_per_second"])
    report = {
        "artifact_type": POINT_ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "prefill_chunk": chunk,
        "prefill_chunk_when_decoding": chunk_when_decoding,
        "command": command,
        "server_instance_id": server_instance_id,
        "weights_id": weights_id,
        "artifact_target": artifact_target,
        "engine": server_start.get("engine", {}),
        "environment": server_start.get("environment", {}),
        "workload": {
            "anchor_prompt_targets": list(profile.anchor_prompt_tokens),
            "anchor_prompt_actual": [
                prompt_cache[("anchor", target)][1] for target in profile.anchor_prompt_tokens
            ],
            "interferer_prompt_target": profile.interferer_prompt_tokens,
            "interferer_prompt_actual": interferer_count,
            "requested_output_tokens": profile.requested_output_tokens,
            "overlap_measurement_seconds": profile.overlap_seconds,
            "main_kv_reservation_tokens": actual_reservations[0],
            "backend_kv_reservation_tokens": actual_reservations[1],
        },
        "baseline": baseline,
        "overlap": overlap,
        "overlap_end_reason": overlap_end_reason,
        "interferer_ttft_seconds": (
            interferer.first_event_at - interferer.started_at if interferer is not None else None
        ),
        "decode_retention": overlap_decode / baseline_decode if baseline_decode > 0 else None,
    }
    point_path = output_dir / "points" / f"{point_name}.json"
    point_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        f"done chunk={chunk}/{chunk_when_decoding}: baseline={baseline_decode:.1f}tok/s "
        f"overlap={overlap_decode:.1f}tok/s retention={report['decode_retention']:.1%}",
        flush=True,
    )
    return report


def write_summary(reports: Sequence[dict[str, Any]], output_dir: Path) -> None:
    summary = {
        "artifact_type": SUMMARY_ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "points": list(reports),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    fields = (
        "prefill_chunk",
        "prefill_chunk_when_decoding",
        "baseline_decode_tokens_per_second",
        "overlap_decode_tokens_per_second",
        "decode_retention",
        "overlap_prefill_tokens_per_second",
        "interferer_ttft_seconds",
    )
    rows = [
        {
            "prefill_chunk": report["prefill_chunk"],
            "prefill_chunk_when_decoding": report["prefill_chunk_when_decoding"],
            "baseline_decode_tokens_per_second": report["baseline"]["decode_tokens_per_second"],
            "overlap_decode_tokens_per_second": report["overlap"]["decode_tokens_per_second"],
            "decode_retention": report["decode_retention"],
            "overlap_prefill_tokens_per_second": report["overlap"]["prefill_tokens_per_second"],
            "interferer_ttft_seconds": report["interferer_ttft_seconds"],
        }
        for report in reports
    ]
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Prefill/decode balance benchmark",
        "",
        "| Prefill chunk | When decoding | Baseline decode tok/s | Overlap decode tok/s | Retention | Prefill tok/s | Interferer TTFT s |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['prefill_chunk']} | {row['prefill_chunk_when_decoding']} | "
            f"{row['baseline_decode_tokens_per_second']:.1f} | "
            f"{row['overlap_decode_tokens_per_second']:.1f} | {row['decode_retention']:.1%} | "
            f"{row['overlap_prefill_tokens_per_second']:.1f} | {row['interferer_ttft_seconds']:.2f} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_partial_summary(
    reports: Sequence[dict[str, Any]], output_dir: Path, failed_chunk: int, error: BaseException
) -> None:
    partial = {
        "artifact_type": SUMMARY_ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "failed_prefill_chunk": failed_chunk,
        "error": str(error),
        "completed_points": list(reports),
    }
    (output_dir / "partial_summary.json").write_text(
        json.dumps(partial, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def reset_summary_state(output_dir: Path) -> None:
    for name in ("summary.json", "summary.csv", "summary.md", "partial_summary.json"):
        path = output_dir / name
        if path.exists():
            path.unlink()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--model-id", default="qwen3.8-27b")
    parser.add_argument("--prefill-chunk", action="append", type=int, dest="chunks")
    parser.add_argument("--prefill-chunk-when-decoding", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    chunks = validate_chunks(args.chunks or [1024, 256, 128])
    if args.prefill_chunk_when_decoding is not None:
        validate_chunks([args.prefill_chunk_when_decoding])
        if args.prefill_chunk_when_decoding > min(chunks):
            raise corpus.CampaignError(
                "--prefill-chunk-when-decoding must not exceed any --prefill-chunk"
            )
    serve = args.serve.expanduser().resolve()
    artifact = args.artifact.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()
    if args.port < 1 or args.port > 65535 or args.device < 0:
        raise corpus.CampaignError("invalid port or device")
    if not args.dry_run:
        if not serve.is_file() or not os.access(serve, os.X_OK):
            raise corpus.CampaignError(f"ninfer-serve is missing or not executable: {serve}")
        if not artifact.is_file():
            raise corpus.CampaignError(f"artifact not found: {artifact}")
        (output_dir / "server").mkdir(parents=True, exist_ok=True)
        (output_dir / "points").mkdir(parents=True, exist_ok=True)
        reset_summary_state(output_dir)
    if args.dry_run:
        for chunk in chunks:
            chunk_when_decoding = args.prefill_chunk_when_decoding or chunk
            log = output_dir / "server" / f"chunk_{chunk}.jsonl"
            print(shlex.join(make_server_command(
                serve,
                artifact,
                log,
                args.model_id,
                args.port,
                args.device,
                chunk,
                chunk_when_decoding,
                DEFAULT_PROFILE,
            )))
        return 0
    reports = []
    for chunk in chunks:
        chunk_when_decoding = args.prefill_chunk_when_decoding or chunk
        try:
            reports.append(
                run_point(
                    serve,
                    artifact,
                    output_dir,
                    args.model_id,
                    args.port,
                    args.device,
                    chunk,
                    chunk_when_decoding,
                    DEFAULT_PROFILE,
                )
            )
        except BaseException as exc:
            write_partial_summary(reports, output_dir, chunk, exc)
            raise
    write_summary(reports, output_dir)
    print(f"summary: {output_dir / 'summary.md'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except corpus.CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130) from None

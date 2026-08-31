#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import os
import re
import shlex
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from config_store import ComposeStore, ConfigConflictError, ConfigError
from history_store import HistoryStore


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
STATIC_ROOT = ROOT / "static"
COMPOSE_PATH = Path(os.environ.get("NINFER_UI_COMPOSE", PROJECT_ROOT / "compose.yaml")).resolve()
NINFER_BASE = os.environ.get("NINFER_UI_TARGET", "http://127.0.0.1:8080").rstrip("/")
CONTAINER_NAME = os.environ.get("NINFER_UI_CONTAINER", "ninfer-4090")
SERVICE_NAME = os.environ.get("NINFER_UI_SERVICE", "ninfer")
BACKUP_DIR = ROOT / "backups"
HISTORY_PATH = Path(os.environ.get("NINFER_UI_HISTORY", ROOT / "history.sqlite3")).resolve()
LAN_API_OVERRIDE = os.environ.get("NINFER_UI_LAN_API", "").strip()
ALLOW_LAN = os.environ.get("NINFER_UI_ALLOW_LAN", "").strip() == "1"
PUBLIC_HOST = os.environ.get("NINFER_UI_PUBLIC_HOST", "").strip().lower()
RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)

THROUGHPUT_RE = re.compile(
    r"throughput interval=(?P<interval>[0-9.]+)s "
    r"prefill=(?P<prefill>[0-9.]+)tok/s decode=(?P<decode>[0-9.]+)tok/s "
    r"running=(?P<running>\d+) prefilling=(?P<prefilling>\d+) "
    r"decode_ready=(?P<decode_ready>\d+) waiting=(?P<waiting>\d+) "
    r"avg_decode_batch=(?P<batch>[0-9.]+|n/a)"
)
REQUEST_DONE_RE = re.compile(
    r"\[req (?P<id>\d+)] done finish=(?P<finish>\S+).*?prompt=(?P<prompt>\d+) "
    r"gen=(?P<gen>\d+) cache=(?P<cache>\d+).*?ttft=(?P<ttft>[0-9]+)ms "
    r".*?prefill=(?P<prefill>[^ ]+) decode=(?P<decode>[^ ]+) "
    r"wall=(?P<wall>[^ ]+).*?speculative=(?P<spec>.+)$"
)


class UiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class SnapshotCache:
    def __init__(self, ttl_seconds: float = 1.5):
        self.ttl_seconds = ttl_seconds
        self.lock = threading.Lock()
        self.timestamp = 0.0
        self.value: dict[str, Any] | None = None

    def get(self) -> dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            if self.value is None or now - self.timestamp >= self.ttl_seconds:
                self.value = collect_snapshot()
                self.timestamp = now
            return self.value

    def invalidate(self) -> None:
        with self.lock:
            self.timestamp = 0.0


STORE = ComposeStore(COMPOSE_PATH, BACKUP_DIR)
CACHE = SnapshotCache()
HISTORY = HistoryStore(HISTORY_PATH)
MUTATION_LOCK = threading.Lock()
REQUEST_BACKFILL_COMPLETE = False


def fetch_text(path: str, timeout: float = 1.5) -> str:
    request = urllib.request.Request(NINFER_BASE + path, headers={"User-Agent": "ninfer-ui/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def fetch_json(path: str, timeout: float = 1.5) -> Any:
    return json.loads(fetch_text(path, timeout))


def host_name(value: str) -> str:
    try:
        return urlparse(f"//{value}").hostname or ""
    except ValueError as exc:
        raise UiError(HTTPStatus.FORBIDDEN, "Host 格式无效") from exc


def bind_host_allowed(host: str) -> bool:
    if host in {"127.0.0.1", "::1"}:
        return True
    return ALLOW_LAN and bool(PUBLIC_HOST) and host == "0.0.0.0"


def rfc1918_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return isinstance(parsed, ipaddress.IPv4Address) and any(
        parsed in network for network in RFC1918_NETWORKS
    )


def public_host_allowed(host: str) -> bool:
    return rfc1918_address(host)


def mutation_client_allowed(address: str) -> bool:
    if address in {"127.0.0.1", "::1"}:
        return True
    if not ALLOW_LAN:
        return False
    return rfc1918_address(address)


def allowed_ui_hosts() -> set[str]:
    hosts = {"127.0.0.1", "localhost", "::1"}
    if ALLOW_LAN and PUBLIC_HOST:
        hosts.add(PUBLIC_HOST)
    return hosts


def allowed_ui_origins(port: int) -> set[str]:
    origins = {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        f"http://[::1]:{port}",
    }
    if ALLOW_LAN and PUBLIC_HOST:
        origin_host = f"[{PUBLIC_HOST}]" if ":" in PUBLIC_HOST else PUBLIC_HOST
        origins.add(f"http://{origin_host}:{port}")
    return origins


def mutation_origin_allowed(origin: str | None, port: int) -> bool:
    if ALLOW_LAN and not origin:
        return False
    return not origin or origin in allowed_ui_origins(port)


def lan_api_url() -> str:
    target = urlparse(LAN_API_OVERRIDE or NINFER_BASE)
    if LAN_API_OVERRIDE:
        if target.scheme not in {"http", "https"} or not target.hostname:
            raise ValueError("NINFER_UI_LAN_API 必须是有效的 HTTP(S) 地址")
        return LAN_API_OVERRIDE.rstrip("/")

    # 保留 loopback 主机名，让前端使用当前浏览器访问管理器时的 hostname
    # 动态生成局域网 API 地址，避免把 WSL/Docker 的历史网关地址当成 LAN 地址。
    port = f":{target.port}" if target.port else ""
    return f"{target.scheme}://{target.hostname}{port}/v1"


def parse_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            metrics[parts[0]] = float(parts[1])
        except ValueError:
            continue
    return metrics


def run_command(command: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def docker_command(args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    direct = ["docker", *args]
    socket = Path("/var/run/docker.sock")
    if socket.exists() and os.access(socket, os.R_OK | os.W_OK):
        return run_command(direct, timeout)
    return run_command(["sg", "docker", "-c", shlex.join(direct)], timeout)


def docker_logs(tail: int = 100) -> list[str]:
    tail = max(1, min(tail, 5_000))
    result = docker_command(
        ["logs", "--timestamps", "--tail", str(tail), CONTAINER_NAME], timeout=8.0
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or "无法读取 Docker 日志")
    return result.stdout.splitlines()


def container_state() -> dict[str, Any]:
    result = docker_command(
        ["inspect", "--format", "{{json .State}}", CONTAINER_NAME], timeout=5.0
    )
    if result.returncode != 0:
        return {"available": False, "error": result.stdout.strip()}
    try:
        state = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"available": False, "error": "Docker 返回了无效状态"}
    return {
        "available": True,
        "status": state.get("Status"),
        "running": bool(state.get("Running")),
        "started_at": state.get("StartedAt"),
        "restart_count": state.get("RestartCount", 0),
        "exit_code": state.get("ExitCode"),
        "error": state.get("Error") or "",
    }


def gpu_state() -> dict[str, Any]:
    fields = (
        "name,utilization.gpu,memory.used,memory.total,memory.free,temperature.gpu,"
        "power.draw,power.limit,clocks.sm"
    )
    result = run_command(
        ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"], timeout=5.0
    )
    if result.returncode != 0:
        return {"available": False, "error": result.stdout.strip()}
    row = [part.strip() for part in result.stdout.splitlines()[0].split(",")]
    if len(row) != 9:
        return {"available": False, "error": "无法解析 nvidia-smi 输出"}
    try:
        return {
            "available": True,
            "name": row[0],
            "utilization": float(row[1]),
            "memory_used_mib": float(row[2]),
            "memory_total_mib": float(row[3]),
            "memory_free_mib": float(row[4]),
            "temperature_c": float(row[5]),
            "power_w": float(row[6]),
            "power_limit_w": float(row[7]),
            "clock_mhz": float(row[8]),
        }
    except ValueError:
        return {"available": False, "error": "nvidia-smi 包含非数值字段"}


def docker_timestamp_ms(line: str) -> int:
    try:
        timestamp_text = line.split(" ", 1)[0]
        if timestamp_text.endswith("Z") and "." in timestamp_text:
            prefix, fraction = timestamp_text[:-1].split(".", 1)
            timestamp_text = f"{prefix}.{fraction[:6]}+00:00"
        else:
            timestamp_text = timestamp_text.replace("Z", "+00:00")
        return int(datetime.fromisoformat(timestamp_text).timestamp() * 1000)
    except (ValueError, OverflowError):
        return 0


def latest_throughput(lines: list[str]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for line in lines:
        match = THROUGHPUT_RE.search(line)
        if not match:
            continue
        values = match.groupdict()
        candidate = {
            "timestamp_ms": docker_timestamp_ms(line),
            "interval_seconds": float(values["interval"]),
            "prefill_tokens_per_second": float(values["prefill"]),
            "decode_tokens_per_second": float(values["decode"]),
            "running": int(values["running"]),
            "prefilling": int(values["prefilling"]),
            "decode_ready": int(values["decode_ready"]),
            "waiting": int(values["waiting"]),
            "average_decode_batch": None
            if values["batch"] == "n/a"
            else float(values["batch"]),
            "line": line,
        }
        if latest is None or candidate["timestamp_ms"] > latest["timestamp_ms"]:
            latest = candidate
    return latest


def current_throughput(
    throughput: dict[str, Any] | None, now_ms: int
) -> dict[str, Any] | None:
    if not isinstance(throughput, dict):
        return None
    interval_ms = max(
        2_000.0, float(throughput.get("interval_seconds", 2.0)) * 1000.0
    )
    source_ms = int(throughput.get("timestamp_ms", 0))
    if source_ms <= 0 or abs(now_ms - source_ms) > interval_ms * 2.5:
        return None
    return throughput


def history_rates(snapshot: dict[str, Any]) -> tuple[float, float]:
    throughput = current_throughput(
        snapshot.get("throughput"), int(snapshot.get("timestamp_ms", 0))
    )
    if throughput is None:
        return 0.0, 0.0
    return (
        max(0.0, float(throughput.get("decode_tokens_per_second", 0.0))),
        max(0.0, float(throughput.get("prefill_tokens_per_second", 0.0))),
    )


class HistorySampler:
    def __init__(self, interval_seconds: float = 2.0):
        self.interval_seconds = interval_seconds
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, name="ninfer-history", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()
        self.thread.join(timeout=max(30.0, self.interval_seconds * 3))
        if self.thread.is_alive():
            raise RuntimeError("吞吐历史采样线程未能按时停止")

    def _run(self) -> None:
        while not self.stopping.is_set():
            try:
                snapshot = CACHE.get()
                decode_rate, prefill_rate = history_rates(snapshot)
                HISTORY.record(int(time.time() * 1000), decode_rate, prefill_rate)
            except (
                OSError,
                ValueError,
                RuntimeError,
                sqlite3.Error,
                subprocess.SubprocessError,
            ) as exc:
                print(f"[ninfer-ui] 吞吐历史采样失败: {exc}", flush=True)
            self.stopping.wait(self.interval_seconds)


def request_events(lines: list[str], limit: int = 12) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        request_line, separator, client_suffix = line.partition(" client_ip=")
        match = REQUEST_DONE_RE.search(request_line)
        if not match:
            continue
        values = match.groupdict()
        client: dict[str, str] = {}
        if separator:
            try:
                for item in shlex.split(f"client_ip={client_suffix}"):
                    key, delimiter, value = item.partition("=")
                    if delimiter:
                        client[key] = value
            except ValueError:
                client = {}
        try:
            client_port = int(client.get("client_port", "-1"))
        except ValueError:
            client_port = -1
        prompt_tokens = int(values["prompt"])
        cache_tokens = int(values["cache"])
        events.append(
            {
                "id": int(values["id"]),
                "finish": values["finish"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": int(values["gen"]),
                "cache_tokens": cache_tokens,
                "cache_hit_rate": cache_tokens / prompt_tokens * 100.0
                if prompt_tokens > 0
                else 0.0,
                "ttft_ms": int(values["ttft"]),
                "prefill": values["prefill"],
                "decode": values["decode"],
                "wall": values["wall"],
                "speculative": values["spec"],
                "client_ip": client.get("client_ip", ""),
                "client_port": client_port,
                "client_id": client.get("client_id", ""),
                "agent_id": client.get("agent_id", ""),
                "session_id": client.get("session_id", ""),
                "user_agent": client.get("user_agent", ""),
                "timestamp_ms": docker_timestamp_ms(line),
                "line": line,
            }
        )
    events.sort(key=lambda event: event["timestamp_ms"], reverse=True)
    return events[:limit]


def reconcile_slot_kv_usage(metrics: dict[str, float], slots: Any) -> None:
    """Use one /slots boundary for both per-lane and total Main KV occupancy."""
    if not isinstance(slots, list) or not slots:
        return
    if any(not isinstance(slot, dict) or "n_kv_tokens" not in slot for slot in slots):
        return
    values = [slot["n_kv_tokens"] for slot in slots]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("NInfer /slots 返回了无效的 n_kv_tokens")
    used = sum(values)
    capacity = metrics.get("ninfer:kv_cache_capacity_tokens")
    if capacity is not None and used > capacity:
        raise ValueError("逐槽 Main KV 占用之和超过共享缓存容量")
    metrics["ninfer:kv_cache_used_tokens"] = float(used)


def collect_snapshot() -> dict[str, Any]:
    global REQUEST_BACKFILL_COMPLETE
    result: dict[str, Any] = {
        "timestamp_ms": int(time.time() * 1000),
        "target": NINFER_BASE,
        "lan_api_url": lan_api_url(),
        "service": {"online": False},
        "metrics": {},
        "slots": [],
        "models": [],
        "gpu": gpu_state(),
        "container": container_state(),
        "throughput": None,
        "recent_requests": [],
        "errors": [],
    }
    try:
        result["service"] = {"online": fetch_json("/health").get("status") == "ok"}
        result["metrics"] = parse_metrics(fetch_text("/metrics"))
        result["slots"] = fetch_json("/slots")
        reconcile_slot_kv_usage(result["metrics"], result["slots"])
        models = fetch_json("/v1/models")
        result["models"] = models.get("data", []) if isinstance(models, dict) else []
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        result["errors"].append(f"NInfer: {exc}")

    try:
        backfill = not REQUEST_BACKFILL_COMPLETE
        current_lines = docker_logs(100)
        result["throughput"] = latest_throughput(current_lines)
        request_lines = current_lines
        if backfill:
            request_lines = [*docker_logs(5_000), *current_lines]
        HISTORY.record_completed_requests(request_events(request_lines, limit=50))
        REQUEST_BACKFILL_COMPLETE = True
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        result["errors"].append(f"Docker logs: {exc}")
    except (ValueError, sqlite3.Error) as exc:
        result["errors"].append(f"Completed requests: {exc}")
    try:
        result["recent_requests"] = HISTORY.recent_completed_requests()
    except (ValueError, sqlite3.Error) as exc:
        result["errors"].append(f"Completed requests: {exc}")
    result["timestamp_ms"] = int(time.time() * 1000)
    result["throughput"] = current_throughput(
        result["throughput"], result["timestamp_ms"]
    )
    return result


def _wait_for_ninfer_health(output: str) -> dict[str, Any]:
    deadline = time.monotonic() + 90.0
    last_error = ""
    while time.monotonic() < deadline:
        try:
            health = fetch_json("/health", timeout=2.0)
            if not isinstance(health, dict):
                raise ValueError("健康检查返回的 JSON 不是对象")
            if health.get("status") == "ok":
                CACHE.invalidate()
                return {"ok": True, "output": output.strip(), "health": "ok", "running": True}
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1.0)
    raise RuntimeError(f"容器已启动，但 90 秒内健康检查未通过: {last_error}")


def start_ninfer() -> dict[str, Any]:
    state = container_state()
    error = str(state.get("error", ""))
    if state.get("available") and state.get("running"):
        raise UiError(HTTPStatus.CONFLICT, "NInfer 已经在运行")
    if not state.get("available") and "no such" not in error.lower():
        raise RuntimeError(error or "启动前无法确认容器状态")
    result = docker_command(
        ["compose", "--file", str(COMPOSE_PATH), "up", "-d", SERVICE_NAME],
        timeout=150.0,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or "Docker Compose 启动失败")
    return _wait_for_ninfer_health(result.stdout)


def stop_ninfer() -> dict[str, Any]:
    before = container_state()
    if not before.get("available"):
        raise RuntimeError(before.get("error") or "停止前无法确认容器状态")
    if not before.get("running"):
        raise UiError(HTTPStatus.CONFLICT, "NInfer 已经停止")
    result = docker_command(
        ["compose", "--file", str(COMPOSE_PATH), "stop", SERVICE_NAME],
        timeout=90.0,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or "Docker Compose 停止失败")
    state = container_state()
    if not state.get("available"):
        raise RuntimeError(state.get("error") or "停止后无法确认容器状态")
    if state.get("running"):
        raise RuntimeError("Docker Compose 已返回成功，但 NInfer 容器仍在运行")
    CACHE.invalidate()
    return {"ok": True, "output": result.stdout.strip(), "running": False}


def restart_ninfer() -> dict[str, Any]:
    state = container_state()
    if not state.get("available"):
        raise RuntimeError(state.get("error") or "重启前无法确认容器状态")
    if not state.get("running"):
        raise UiError(HTTPStatus.CONFLICT, "NInfer 已停止，请使用启动操作")
    result = docker_command(
        [
            "compose",
            "--file",
            str(COMPOSE_PATH),
            "up",
            "-d",
            "--force-recreate",
            SERVICE_NAME,
        ],
        timeout=150.0,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or "Docker Compose 重启失败")

    return _wait_for_ninfer_health(result.stdout)


class UiHandler(BaseHTTPRequestHandler):
    server_version = "NInferUI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[ninfer-ui] {self.address_string()} {fmt % args}")

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
            "script-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        )

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_safe_mutation(self) -> None:
        if not mutation_client_allowed(self.client_address[0]):
            raise UiError(HTTPStatus.FORBIDDEN, "客户端地址不在管理白名单")
        host = host_name(self.headers.get("Host", ""))
        if host not in allowed_ui_hosts():
            raise UiError(HTTPStatus.FORBIDDEN, "Host 不在管理白名单")
        origin = self.headers.get("Origin")
        if not mutation_origin_allowed(origin, self.server.server_port):
            raise UiError(HTTPStatus.FORBIDDEN, "Origin 不在管理白名单")
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise UiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "必须使用 application/json")

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise UiError(HTTPStatus.BAD_REQUEST, "Content-Length 无效") from exc
        if length <= 0 or length > 64 * 1024:
            raise UiError(HTTPStatus.BAD_REQUEST, "请求体大小无效")
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise UiError(HTTPStatus.BAD_REQUEST, "JSON 无效") from exc
        if not isinstance(value, dict):
            raise UiError(HTTPStatus.BAD_REQUEST, "JSON 顶层必须是对象")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/snapshot":
                self._send_json(HTTPStatus.OK, CACHE.get())
                return
            if parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                period = query.get("range", ["realtime"])[0]
                try:
                    anchor_values = query.get("anchor_ms")
                    anchor_ms = int(anchor_values[0]) if anchor_values else None
                    detail_start_values = query.get("detail_start_ms")
                    detail_end_values = query.get("detail_end_ms")
                    detail_start_ms = (
                        int(detail_start_values[0]) if detail_start_values else None
                    )
                    detail_end_ms = int(detail_end_values[0]) if detail_end_values else None
                    payload = HISTORY.query(
                        period,
                        int(time.time() * 1000),
                        anchor_ms,
                        detail_start_ms,
                        detail_end_ms,
                    )
                except ValueError as exc:
                    raise UiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/config":
                _, config, revision = STORE.read()
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "config": config,
                        "revision": revision,
                        "compose_path": str(COMPOSE_PATH),
                    },
                )
                return
            if parsed.path == "/api/logs":
                query = parse_qs(parsed.query)
                try:
                    tail = int(query.get("tail", ["120"])[0])
                except ValueError:
                    tail = 120
                lines = docker_logs(tail)
                self._send_json(HTTPStatus.OK, {"lines": lines})
                return
            if parsed.path in {"/", "/index.html"}:
                self._send_file(STATIC_ROOT / "index.html")
                return
            if parsed.path.startswith("/static/"):
                relative = parsed.path.removeprefix("/static/")
                target = (STATIC_ROOT / relative).resolve()
                if STATIC_ROOT not in target.parents:
                    raise UiError(HTTPStatus.FORBIDDEN, "路径无效")
                self._send_file(target)
                return
            raise UiError(HTTPStatus.NOT_FOUND, "页面不存在")
        except UiError as exc:
            self._send_json(exc.status, {"error": str(exc)})
        except (
            ConfigError,
            OSError,
            RuntimeError,
            sqlite3.Error,
            subprocess.SubprocessError,
        ) as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            self._require_safe_mutation()
            body = self._read_json()
            if parsed.path == "/api/config/apply":
                if body.get("confirmation") != "APPLY CONFIG":
                    raise UiError(HTTPStatus.BAD_REQUEST, "确认文本不正确")
                with MUTATION_LOCK:
                    result = STORE.apply(
                        body.get("config", {}), str(body.get("revision", ""))
                    )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "changed": bool(result.diff),
                        "revision": result.revision,
                        "message": "配置已保存；运行中的服务尚未改变",
                    },
                )
                return
            if parsed.path == "/api/restart":
                if body.get("confirmation") != "RESTART NINFER":
                    raise UiError(HTTPStatus.BAD_REQUEST, "确认文本不正确")
                with MUTATION_LOCK:
                    result = restart_ninfer()
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/start":
                if body.get("confirmation") != "START NINFER":
                    raise UiError(HTTPStatus.BAD_REQUEST, "确认文本不正确")
                with MUTATION_LOCK:
                    result = start_ninfer()
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/stop":
                if body.get("confirmation") != "STOP NINFER":
                    raise UiError(HTTPStatus.BAD_REQUEST, "确认文本不正确")
                with MUTATION_LOCK:
                    result = stop_ninfer()
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/history/clear":
                if body.get("confirmation") != "DELETE HISTORY":
                    raise UiError(HTTPStatus.BAD_REQUEST, "确认文本不正确")
                start_date = str(body.get("start_date", ""))
                end_date = str(body.get("end_date", ""))
                try:
                    with MUTATION_LOCK:
                        deleted = HISTORY.clear_dates(start_date, end_date)
                except ValueError as exc:
                    raise UiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
                self._send_json(
                    HTTPStatus.OK,
                    {"ok": True, "deleted": deleted},
                )
                return
            raise UiError(HTTPStatus.NOT_FOUND, "接口不存在")
        except ConfigConflictError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except ConfigError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except UiError as exc:
            self._send_json(exc.status, {"error": str(exc)})
        except (OSError, RuntimeError, sqlite3.Error, subprocess.SubprocessError) as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="NInfer local monitoring and control UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8081, type=int)
    args = parser.parse_args()
    if args.host == "0.0.0.0" and ALLOW_LAN and not PUBLIC_HOST:
        raise SystemExit("局域网模式必须设置 NINFER_UI_PUBLIC_HOST")
    if not bind_host_allowed(args.host):
        raise SystemExit(
            "ninfer_ui 默认只允许绑定回环地址；局域网模式需设置 NINFER_UI_ALLOW_LAN=1"
        )
    if ALLOW_LAN and not public_host_allowed(PUBLIC_HOST):
        raise SystemExit("NINFER_UI_PUBLIC_HOST 必须是 RFC1918 IPv4 地址")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port 必须在 1..65535 之间")
    if not COMPOSE_PATH.is_file():
        raise SystemExit(f"compose.yaml 不存在: {COMPOSE_PATH}")

    server = ThreadingHTTPServer((args.host, args.port), UiHandler)
    history_sampler = HistorySampler()
    print(f"NInfer UI listening on http://{args.host}:{args.port}")
    print(f"Target: {NINFER_BASE} | Compose: {COMPOSE_PATH}")
    history_sampler.start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        history_sampler.stop()


if __name__ == "__main__":
    main()

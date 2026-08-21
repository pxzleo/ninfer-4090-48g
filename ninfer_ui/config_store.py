from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NATIVE_CONTEXT = 262_144
KV_DTYPES = ("bf16", "int8", "rk8v4", "rk4v4", "rk4v4-e8", "rk2v4-e8")
SPEC_MODES = ("off", "mtp")
REASONING_EFFORTS = ("none", "low", "medium", "xhigh")


class ConfigError(ValueError):
    pass


class ConfigConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConfigPreview:
    revision: str
    config: dict[str, Any]
    rendered: str
    diff: str


def revision_for(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _decode_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        if value[0] == '"':
            return str(json.loads(value))
        return value[1:-1].replace("''", "'")
    return value


def _encode_scalar(value: str) -> str:
    if re.fullmatch(r"[0-9]+", value):
        return json.dumps(value)
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        return value
    return json.dumps(value, ensure_ascii=False)


def command_block(text: str) -> tuple[int, int, list[str]]:
    lines = text.splitlines(keepends=True)
    service_start = None
    service_end = len(lines)
    for index, line in enumerate(lines):
        if re.fullmatch(r"  ninfer:\s*\n?", line):
            service_start = index
            break
    if service_start is None:
        raise ConfigError("compose.yaml 中没有 services.ninfer")

    for index in range(service_start + 1, len(lines)):
        if re.fullmatch(r"  [A-Za-z0-9_.-]+:\s*\n?", lines[index]):
            service_end = index
            break

    command_line = None
    for index in range(service_start + 1, service_end):
        if re.fullmatch(r"    command:\s*\n?", lines[index]):
            command_line = index
            break
    if command_line is None:
        raise ConfigError("compose.yaml 中没有 services.ninfer.command")

    start = command_line + 1
    end = start
    tokens: list[str] = []
    while end < service_end:
        match = re.fullmatch(r"      -\s+(.+?)\s*\n?", lines[end])
        if not match:
            break
        tokens.append(_decode_scalar(match.group(1)))
        end += 1
    if len(tokens) < 2 or tokens[0] != "ninfer-serve":
        raise ConfigError("ninfer command 必须使用 YAML 列表形式并以 ninfer-serve 开头")
    return start, end, tokens


def _option_map(tokens: list[str]) -> tuple[dict[str, str], set[str]]:
    values: dict[str, str] = {}
    flags: set[str] = set()
    index = 2
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            raise ConfigError(f"无法解析 command token: {token}")
        if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
            values[token] = tokens[index + 1]
            index += 2
        else:
            flags.add(token)
            index += 1
    return values, flags


def _required_int(values: dict[str, str], option: str, default: int) -> int:
    raw = values.get(option, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{option} 必须是整数") from exc


def parse_config(text: str) -> dict[str, Any]:
    _, _, tokens = command_block(text)
    values, flags = _option_map(tokens)
    if "--no-thinking" in flags and "--reasoning-effort" in values:
        raise ConfigError("--no-thinking 不能与 --reasoning-effort 同时使用")
    if "--reasoning-language" in flags:
        raise ConfigError("--reasoning-language 在 compose.yaml 中缺少值")
    reasoning_language = values.get("--reasoning-language")
    if reasoning_language not in (None, "en-US", "zh-CN"):
        raise ConfigError("--reasoning-language 只支持 en-US 或 zh-CN")
    if "--no-thinking" in flags and reasoning_language is not None:
        raise ConfigError("关闭思考时不能指定思考语言")
    spec = values.get("--spec", "off")
    return {
        "max_context": _required_int(values, "--max-context", 8192),
        "kv_capacity": values.get("--kv-capacity", values.get("--max-context", "8192")),
        "max_concurrency": _required_int(values, "--max-concurrency", 1),
        "max_pending_requests": _required_int(values, "--max-pending-requests", 16),
        "pending_timeout_ms": _required_int(values, "--pending-timeout-ms", 30_000),
        "prefill_chunk": _required_int(values, "--prefill-chunk", 1024),
        "kv_dtype": values.get("--kv-dtype", "bf16"),
        "spec": spec,
        "draft_tokens": _required_int(values, "--draft-tokens", 3),
        "lm_head_draft": "--lm-head-draft" in flags,
        "vision": "--vision" in flags,
        "preserve_thinking": "--preserve-thinking" in flags,
        "reasoning_effort": (
            "none" if "--no-thinking" in flags else values.get("--reasoning-effort", "xhigh")
        ),
        "chinese_reasoning": reasoning_language == "zh-CN",
        "prefix_reuse": "--no-prefix-reuse" not in flags,
        "cuda_graph": "--no-cuda-graph" not in flags,
        "log_stats_interval_ms": _required_int(values, "--log-stats-interval-ms", 5000),
        "default_max_tokens": _required_int(values, "--default-max-tokens", 8192),
    }


def _int_field(config: dict[str, Any], name: str) -> int:
    value = config.get(name)
    if isinstance(value, bool):
        raise ConfigError(f"{name} 必须是整数")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} 必须是整数") from exc


def _bool_field(config: dict[str, Any], name: str) -> bool:
    value = config.get(name)
    if not isinstance(value, bool):
        raise ConfigError(f"{name} 必须是布尔值")
    return value


def validate_config(candidate: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "max_context",
        "kv_capacity",
        "max_concurrency",
        "max_pending_requests",
        "pending_timeout_ms",
        "prefill_chunk",
        "kv_dtype",
        "spec",
        "draft_tokens",
        "lm_head_draft",
        "vision",
        "preserve_thinking",
        "reasoning_effort",
        "chinese_reasoning",
        "prefix_reuse",
        "cuda_graph",
        "log_stats_interval_ms",
        "default_max_tokens",
    }
    unknown = sorted(set(candidate) - allowed)
    missing = sorted(allowed - set(candidate))
    if unknown:
        raise ConfigError("不支持的配置字段: " + ", ".join(unknown))
    if missing:
        raise ConfigError("缺少配置字段: " + ", ".join(missing))

    max_context = _int_field(candidate, "max_context")
    if not 1 <= max_context <= NATIVE_CONTEXT:
        raise ConfigError(f"max_context 必须在 1..{NATIVE_CONTEXT} 之间")

    max_concurrency = _int_field(candidate, "max_concurrency")
    if not 1 <= max_concurrency <= 8:
        raise ConfigError("max_concurrency 必须在 1..8 之间")

    kv_capacity_raw = str(candidate["kv_capacity"]).strip().lower()
    if kv_capacity_raw == "auto":
        kv_capacity = "auto"
    else:
        try:
            kv_capacity_value = int(kv_capacity_raw)
        except ValueError as exc:
            raise ConfigError("kv_capacity 必须是 auto 或正整数") from exc
        if kv_capacity_value < max_context:
            raise ConfigError("kv_capacity 不能小于 max_context")
        max_shared = max_concurrency * max_context
        if kv_capacity_value > max_shared:
            raise ConfigError("kv_capacity 不能超过 max_concurrency × max_context")
        kv_capacity = str(kv_capacity_value)

    max_pending = _int_field(candidate, "max_pending_requests")
    if not 1 <= max_pending <= 1024:
        raise ConfigError("max_pending_requests 必须在 1..1024 之间")
    timeout = _int_field(candidate, "pending_timeout_ms")
    if not 1 <= timeout <= 3_600_000:
        raise ConfigError("pending_timeout_ms 必须在 1..3600000 之间")
    prefill = _int_field(candidate, "prefill_chunk")
    if prefill <= 0 or prefill > max_context or prefill % 128 != 0:
        raise ConfigError("prefill_chunk 必须是不超过 max_context 的 128 倍数")
    default_max = _int_field(candidate, "default_max_tokens")
    if not 1 <= default_max <= max_context:
        raise ConfigError("default_max_tokens 必须在 1..max_context 之间")
    stats_interval = _int_field(candidate, "log_stats_interval_ms")
    if not 0 <= stats_interval <= 600_000:
        raise ConfigError("log_stats_interval_ms 必须在 0..600000 之间")

    kv_dtype = str(candidate["kv_dtype"])
    if kv_dtype not in KV_DTYPES:
        raise ConfigError("不支持的 kv_dtype")
    spec = str(candidate["spec"])
    if spec not in SPEC_MODES:
        raise ConfigError("spec 只支持 off 或 mtp")
    draft_tokens = _int_field(candidate, "draft_tokens")
    if spec == "mtp" and not 1 <= draft_tokens <= 5:
        raise ConfigError("MTP draft_tokens 必须在 1..5 之间")
    if spec == "off" and _bool_field(candidate, "lm_head_draft"):
        raise ConfigError("关闭 MTP 时不能启用 lm_head_draft")
    reasoning_effort = str(candidate["reasoning_effort"])
    if reasoning_effort not in REASONING_EFFORTS:
        raise ConfigError("reasoning_effort 只支持 none、low、medium 或 xhigh")
    chinese_reasoning = _bool_field(candidate, "chinese_reasoning")
    if reasoning_effort == "none" and chinese_reasoning:
        raise ConfigError("关闭思考时不能启用中文思考")

    return {
        "max_context": max_context,
        "kv_capacity": kv_capacity,
        "max_concurrency": max_concurrency,
        "max_pending_requests": max_pending,
        "pending_timeout_ms": timeout,
        "prefill_chunk": prefill,
        "kv_dtype": kv_dtype,
        "spec": spec,
        "draft_tokens": draft_tokens,
        "lm_head_draft": _bool_field(candidate, "lm_head_draft"),
        "vision": _bool_field(candidate, "vision"),
        "preserve_thinking": _bool_field(candidate, "preserve_thinking"),
        "reasoning_effort": reasoning_effort,
        "chinese_reasoning": chinese_reasoning,
        "prefix_reuse": _bool_field(candidate, "prefix_reuse"),
        "cuda_graph": _bool_field(candidate, "cuda_graph"),
        "log_stats_interval_ms": stats_interval,
        "default_max_tokens": default_max,
    }


def _replace_value(tokens: list[str], option: str, value: str) -> None:
    if option in tokens:
        index = tokens.index(option)
        if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
            raise ConfigError(f"{option} 在 compose.yaml 中缺少值")
        tokens[index + 1] = value
        return
    tokens.extend((option, value))


def _set_flag(tokens: list[str], option: str, enabled: bool) -> None:
    if enabled and option not in tokens:
        tokens.append(option)
        return
    if not enabled:
        while option in tokens:
            tokens.remove(option)


def _remove_value(tokens: list[str], option: str) -> None:
    while option in tokens:
        index = tokens.index(option)
        del tokens[index]
        if index < len(tokens) and not tokens[index].startswith("--"):
            del tokens[index]


def render_config(text: str, candidate: dict[str, Any]) -> str:
    config = validate_config(candidate)
    start, end, tokens = command_block(text)
    lines = text.splitlines(keepends=True)

    value_options = {
        "--max-context": str(config["max_context"]),
        "--kv-capacity": str(config["kv_capacity"]),
        "--max-concurrency": str(config["max_concurrency"]),
        "--max-pending-requests": str(config["max_pending_requests"]),
        "--pending-timeout-ms": str(config["pending_timeout_ms"]),
        "--prefill-chunk": str(config["prefill_chunk"]),
        "--kv-dtype": str(config["kv_dtype"]),
    }
    for option, value in value_options.items():
        _replace_value(tokens, option, value)
    optional_values = {
        "--log-stats-interval-ms": (str(config["log_stats_interval_ms"]), "5000"),
        "--default-max-tokens": (str(config["default_max_tokens"]), "8192"),
    }
    for option, (value, default) in optional_values.items():
        if option in tokens or value != default:
            _replace_value(tokens, option, value)

    if config["spec"] == "mtp":
        _replace_value(tokens, "--spec", "mtp")
        _replace_value(tokens, "--draft-tokens", str(config["draft_tokens"]))
    else:
        _remove_value(tokens, "--spec")
        _remove_value(tokens, "--draft-tokens")

    _set_flag(tokens, "--lm-head-draft", bool(config["lm_head_draft"]))
    _set_flag(tokens, "--vision", bool(config["vision"]))
    _set_flag(tokens, "--preserve-thinking", bool(config["preserve_thinking"]))
    if config["reasoning_effort"] == "none":
        _remove_value(tokens, "--reasoning-effort")
        _set_flag(tokens, "--no-thinking", True)
    else:
        _set_flag(tokens, "--no-thinking", False)
        _replace_value(tokens, "--reasoning-effort", str(config["reasoning_effort"]))
    if config["reasoning_effort"] == "none":
        _remove_value(tokens, "--reasoning-language")
    elif config["chinese_reasoning"]:
        _replace_value(tokens, "--reasoning-language", "zh-CN")
    else:
        _replace_value(tokens, "--reasoning-language", "en-US")
    _set_flag(tokens, "--no-prefix-reuse", not bool(config["prefix_reuse"]))
    _set_flag(tokens, "--no-cuda-graph", not bool(config["cuda_graph"]))

    rendered_block = [f"      - {_encode_scalar(token)}\n" for token in tokens]
    return "".join(lines[:start] + rendered_block + lines[end:])


def preview(text: str, candidate: dict[str, Any]) -> ConfigPreview:
    normalized = validate_config(candidate)
    rendered = render_config(text, normalized)
    diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile="compose.yaml (current)",
            tofile="compose.yaml (proposed)",
        )
    )
    return ConfigPreview(
        revision=revision_for(text), config=normalized, rendered=rendered, diff=diff
    )


class ComposeStore:
    def __init__(self, path: Path, backup_dir: Path):
        self.path = path
        self.backup_dir = backup_dir

    def read(self) -> tuple[str, dict[str, Any], str]:
        text = self.path.read_text(encoding="utf-8")
        return text, parse_config(text), revision_for(text)

    def preview(self, candidate: dict[str, Any]) -> ConfigPreview:
        text = self.path.read_text(encoding="utf-8")
        return preview(text, candidate)

    def apply(self, candidate: dict[str, Any], expected_revision: str) -> ConfigPreview:
        text = self.path.read_text(encoding="utf-8")
        current_revision = revision_for(text)
        if current_revision != expected_revision:
            raise ConfigConflictError("compose.yaml 已被其他进程修改，请刷新后重试")
        result = preview(text, candidate)
        if not result.diff:
            return result

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self.backup_dir / f"compose-{stamp}-{current_revision}.yaml"
        backup.write_text(text, encoding="utf-8")

        descriptor, temp_name = tempfile.mkstemp(
            prefix=".compose.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(result.rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return result

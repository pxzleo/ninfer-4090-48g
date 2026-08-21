from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config_store import (  # noqa: E402
    ComposeStore,
    ConfigConflictError,
    ConfigError,
    parse_config,
    preview,
    revision_for,
)


COMPOSE = """services:
  ninfer:
    image: ninfer-4090:sm89
    command:
      - ninfer-serve
      - models/qwen3_8_27b.ninfer
      - --host
      - 0.0.0.0
      - --port
      - "8080"
      - --max-context
      - "262144"
      - --kv-capacity
      - "262144"
      - --max-concurrency
      - "4"
      - --max-pending-requests
      - "16"
      - --pending-timeout-ms
      - "600000"
      - --prefill-chunk
      - "1024"
      - --kv-dtype
      - int8
      - --spec
      - mtp
      - --draft-tokens
      - "3"
      - --lm-head-draft
      - --vision
      - --preserve-thinking
"""


class ConfigStoreTest(unittest.TestCase):
    def test_round_trip_materializes_default_reasoning_effort(self) -> None:
        config = parse_config(COMPOSE)
        result = preview(COMPOSE, config)
        self.assertIn("--reasoning-effort\n      - xhigh", result.rendered)
        self.assertEqual(parse_config(result.rendered)["reasoning_effort"], "xhigh")

    def test_updates_capacity_and_concurrency(self) -> None:
        config = parse_config(COMPOSE)
        config["max_concurrency"] = 8
        config["kv_capacity"] = "524288"
        result = preview(COMPOSE, config)
        updated = parse_config(result.rendered)
        self.assertEqual(updated["max_concurrency"], 8)
        self.assertEqual(updated["kv_capacity"], "524288")
        self.assertIn('      - "524288"', result.diff)

    def test_rejects_native_context_overflow(self) -> None:
        config = parse_config(COMPOSE)
        config["max_context"] = 262145
        with self.assertRaisesRegex(ConfigError, "max_context"):
            preview(COMPOSE, config)

    def test_rejects_impossible_shared_capacity(self) -> None:
        config = parse_config(COMPOSE)
        config["max_concurrency"] = 2
        config["kv_capacity"] = str(3 * 262144)
        with self.assertRaisesRegex(ConfigError, "max_concurrency"):
            preview(COMPOSE, config)

    def test_disabling_mtp_removes_dependent_options(self) -> None:
        config = parse_config(COMPOSE)
        config["spec"] = "off"
        config["lm_head_draft"] = False
        result = preview(COMPOSE, config)
        self.assertNotIn("--spec", result.rendered)
        self.assertNotIn("--draft-tokens", result.rendered)
        self.assertNotIn("--lm-head-draft", result.rendered)

    def test_updates_qwen38_reasoning_effort(self) -> None:
        config = parse_config(COMPOSE)
        self.assertEqual(config["reasoning_effort"], "xhigh")
        config["reasoning_effort"] = "medium"
        result = preview(COMPOSE, config)
        self.assertIn("--reasoning-effort", result.rendered)
        self.assertEqual(parse_config(result.rendered)["reasoning_effort"], "medium")

    def test_chinese_reasoning_toggle_defaults_off_and_round_trips(self) -> None:
        config = parse_config(COMPOSE)
        self.assertFalse(config["chinese_reasoning"])

        config["chinese_reasoning"] = True
        enabled = preview(COMPOSE, config)
        self.assertIn("--reasoning-language\n      - zh-CN", enabled.rendered)
        self.assertTrue(parse_config(enabled.rendered)["chinese_reasoning"])

        config = parse_config(enabled.rendered)
        config["chinese_reasoning"] = False
        disabled = preview(enabled.rendered, config)
        self.assertIn("--reasoning-language\n      - en-US", disabled.rendered)
        self.assertFalse(parse_config(disabled.rendered)["chinese_reasoning"])

    def test_rejects_chinese_reasoning_when_thinking_is_off(self) -> None:
        config = parse_config(COMPOSE)
        config["reasoning_effort"] = "none"
        config["chinese_reasoning"] = True
        with self.assertRaisesRegex(ConfigError, "中文思考"):
            preview(COMPOSE, config)

    def test_rejects_unsupported_reasoning_language_in_compose(self) -> None:
        unsupported = COMPOSE + "      - --reasoning-language\n      - fr-FR\n"
        with self.assertRaisesRegex(ConfigError, "reasoning-language"):
            parse_config(unsupported)

    def test_disables_and_reenables_qwen38_reasoning(self) -> None:
        config = parse_config(COMPOSE)
        english = preview(COMPOSE, config)
        self.assertIn("--reasoning-language\n      - en-US", english.rendered)

        config = parse_config(english.rendered)
        config["reasoning_effort"] = "none"
        disabled = preview(english.rendered, config)
        self.assertIn("--no-thinking", disabled.rendered)
        self.assertNotIn("--reasoning-effort", disabled.rendered)
        self.assertNotIn("--reasoning-language", disabled.rendered)
        self.assertEqual(parse_config(disabled.rendered)["reasoning_effort"], "none")

        config = parse_config(disabled.rendered)
        config["reasoning_effort"] = "low"
        enabled = preview(disabled.rendered, config)
        self.assertNotIn("--no-thinking", enabled.rendered)
        self.assertIn("--reasoning-effort", enabled.rendered)
        self.assertEqual(parse_config(enabled.rendered)["reasoning_effort"], "low")

        config = parse_config(disabled.rendered)
        config["reasoning_effort"] = "xhigh"
        high = preview(disabled.rendered, config)
        self.assertNotIn("--no-thinking", high.rendered)
        self.assertIn("--reasoning-effort\n      - xhigh", high.rendered)
        self.assertEqual(parse_config(high.rendered)["reasoning_effort"], "xhigh")

    def test_rejects_conflicting_qwen38_reasoning_options(self) -> None:
        conflicting = COMPOSE + "      - --no-thinking\n      - --reasoning-effort\n      - low\n"
        with self.assertRaisesRegex(ConfigError, "不能与"):
            parse_config(conflicting)

    def test_apply_creates_backup_and_detects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            compose = root / "compose.yaml"
            compose.write_text(COMPOSE, encoding="utf-8")
            store = ComposeStore(compose, root / "backups")
            config = parse_config(COMPOSE)
            config["max_pending_requests"] = 24
            store.apply(config, revision_for(COMPOSE))
            self.assertEqual(parse_config(compose.read_text(encoding="utf-8"))["max_pending_requests"], 24)
            self.assertEqual(len(list((root / "backups").glob("compose-*.yaml"))), 1)
            with self.assertRaises(ConfigConflictError):
                store.apply(config, revision_for(COMPOSE))


if __name__ == "__main__":
    unittest.main()

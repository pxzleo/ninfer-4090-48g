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
    def test_round_trip_without_changes_is_exact(self) -> None:
        config = parse_config(COMPOSE)
        result = preview(COMPOSE, config)
        self.assertEqual(result.diff, "")
        self.assertEqual(result.rendered, COMPOSE)

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

import json
import os
import re
import subprocess
import unittest
from pathlib import Path


APP_JS = Path(__file__).parents[1] / "static" / "app.js"
APP_HTML = Path(__file__).parents[1] / "static" / "index.html"


class SlotStageTest(unittest.TestCase):
    def test_request_rows_open_an_accessible_detail_dialog(self):
        html = APP_HTML.read_text(encoding="utf-8")
        javascript = APP_JS.read_text(encoding="utf-8")

        self.assertIn('id="request-detail-dialog"', html)
        self.assertIn('aria-labelledby="request-detail-title"', html)
        self.assertIn('row.tabIndex = 0', javascript)
        self.assertIn(
            'keyboardEvent.key === "Enter" || keyboardEvent.key === " "', javascript
        )
        self.assertIn("showRequestDetails", javascript)
        self.assertNotIn('request-detail-content").innerHTML', javascript)

    def test_lan_api_address_uses_ui_hostname_and_target_port(self):
        script = f"""
const {{lanApiAddress}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify([
  lanApiAddress("http://127.0.0.1:8080", "192.168.100.149"),
  lanApiAddress("invalid", "192.168.100.149"),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            ["http://192.168.100.149:8080/v1", "—"],
        )

    def render(
        self, slot: dict, throughput: dict | None = None, slot_rate: float | None = None
    ) -> str:
        script = (
            f"const {{slotStage}} = require({json.dumps(str(APP_JS))});"
            f"process.stdout.write(slotStage({json.dumps(slot)}, 0, "
            f"{json.dumps(throughput)}, {json.dumps(slot_rate)}));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def test_prefill_uses_processed_prompt_progress(self):
        slot = {
            "is_processing": True,
            "state": "prefill",
            "n_prompt_tokens": 11492,
            "n_prompt_tokens_processed": 5120,
        }
        self.assertEqual(self.render(slot), "预填充中 · 44.6%")
        slot["n_prompt_tokens_processed"] = 7168
        self.assertEqual(self.render(slot), "预填充中 · 62.4%")

    def test_idle_slot_uses_cache_wording_in_chinese(self):
        slot = {"is_processing": False, "n_prompt_tokens": 0, "n_kv_tokens": 128}
        self.assertEqual(self.render(slot), "空闲 · 缓存已保留")

    def test_slot_cache_uses_resident_kv_tokens(self):
        script = f"""
const {{slotKvUsage}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(slotKvUsage({{
  n_prompt_tokens: 193848,
  n_kv_tokens: 194112,
  n_ctx: 262144,
}})));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {"used": 194112, "capacity": 262144, "percent": 74.0478515625},
        )

    def test_slot_cache_falls_back_for_old_server(self):
        script = f"""
const {{slotKvUsage}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(slotKvUsage({{
  n_prompt_tokens: 193848,
  n_ctx: 262144,
}})));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout)["used"], 193848)

    def test_prefill_progress_includes_cached_tokens(self):
        slot = {
            "is_processing": True,
            "state": "prefill",
            "n_prompt_tokens": 48788,
            "n_prompt_tokens_cache": 27485,
            "n_prompt_tokens_processed": 41821,
        }
        self.assertEqual(self.render(slot), "预填充中 · 85.7%")

    def test_decode_uses_own_slot_rate(self):
        slot = {"is_processing": True, "state": "decode", "n_prompt_tokens": 100}
        self.assertEqual(
            self.render(slot, {"decode_tokens_per_second": 123.45}, 37.25),
            "解码中 · 37.3 tok/s",
        )

    def test_manual_language_switch_localizes_dynamic_slot_state(self):
        script = f"""
const {{setLanguageMode, slotStage}} = require({json.dumps(str(APP_JS))});
setLanguageMode("en");
const slot = {{is_processing: true, state: "prefill", n_prompt_tokens: 100, n_prompt_tokens_processed: 25}};
process.stdout.write(slotStage(slot, 0, null));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(result.stdout, "Prefilling · 25%")

    def test_auto_language_uses_first_browser_preference(self):
        script = f"""
const {{languageFromPreferences}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify([
  languageFromPreferences(["zh-CN", "en-US"]),
  languageFromPreferences(["en-US", "zh-CN"]),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout), ["zh-CN", "en"])

    def test_storage_security_error_falls_back_without_breaking_ui_module(self):
        script = f"""
Object.defineProperty(globalThis, "window", {{value: {{
  get localStorage() {{ throw new DOMException("denied", "SecurityError"); }}
}}}});
const {{setLanguageMode, slotStage}} = require({json.dumps(str(APP_JS))});
setLanguageMode("en");
process.stdout.write(slotStage({{is_processing: false, n_prompt_tokens: 0}}, 0, null));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(result.stdout, "Idle")

    def test_common_server_errors_are_localized_in_english(self):
        script = f"""
const {{localizeApiError, setLanguageMode}} = require({json.dumps(str(APP_JS))});
setLanguageMode("en");
process.stdout.write(JSON.stringify([
  localizeApiError("compose.yaml 已被其他进程修改，请刷新后重试"),
  localizeApiError("容器已启动，但 90 秒内健康检查未通过: connection refused"),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                "compose.yaml was modified by another process; refresh and try again",
                "The container started, but its health check did not pass within 90 seconds: connection refused",
            ],
        )

    def test_confirmation_dialog_has_accessible_name_and_description(self):
        html = APP_HTML.read_text(encoding="utf-8")
        self.assertIn(
            '<dialog id="confirm-dialog" aria-labelledby="confirm-title" '
            'aria-describedby="confirm-message">',
            html,
        )
        self.assertIn('id="confirm-phrase-row"', html)

    def test_config_apply_and_service_controls_use_plain_confirmation(self):
        script = f"""
const {{configApplyConfirmationOptions, confirmationState, serviceConfirmationOptions}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify({{
  empty: confirmationState(""),
  typed: confirmationState("DELETE HISTORY"),
  apply: configApplyConfirmationOptions(),
  restart: serviceConfirmationOptions("restart"),
  stop: serviceConfirmationOptions("stop"),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        states = json.loads(result.stdout)
        self.assertEqual(
            states["empty"],
            {"phraseRequired": False, "inputHidden": True, "confirmDisabled": False},
        )
        self.assertEqual(
            states["typed"],
            {"phraseRequired": True, "inputHidden": False, "confirmDisabled": True},
        )
        self.assertEqual(states["apply"]["confirmation"], "APPLY CONFIG")
        self.assertEqual(states["restart"]["confirmation"], "RESTART NINFER")
        self.assertEqual(states["stop"]["confirmation"], "STOP NINFER")
        self.assertNotIn("phrase", states["apply"])
        self.assertNotIn("phrase", states["restart"])
        self.assertNotIn("phrase", states["stop"])

    def test_qwen38_reasoning_level_replaces_thinking_toggle(self):
        html = APP_HTML.read_text(encoding="utf-8")
        self.assertIn('<select name="reasoning_effort">', html)
        self.assertIn('<option value="none" data-i18n="settings.reasoningOff">', html)
        self.assertIn('input name="chinese_reasoning" type="checkbox"', html)
        self.assertIn('data-i18n="settings.chineseReasoningHelp"', html)
        self.assertIn(">新建会话生效</p>", html)
        app = APP_JS.read_text(encoding="utf-8")
        self.assertIn('"settings.chineseReasoningHelp": "新建会话生效"', app)
        self.assertNotIn('input name="thinking"', html)

    def test_static_translation_keys_exist_in_both_languages(self):
        script = f"""
const {{I18N}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(I18N));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        translations = json.loads(result.stdout)
        html = APP_HTML.read_text(encoding="utf-8")
        keys = set(re.findall(r'data-i18n(?:-aria|-title)?="([^"]+)"', html))
        self.assertEqual(set(translations["zh-CN"]), set(translations["en"]))
        self.assertFalse(keys - set(translations["zh-CN"]))

    def test_slot_rates_are_derived_per_request(self):
        script = f"""
const {{calculateSlotDecodeRates}} = require({json.dumps(str(APP_JS))});
const previous = {{
  "1": {{requestId: "101", generatedTokens: 20, timestampMs: 1000, serviceInstance: "start-a"}},
  "2": {{requestId: "102", generatedTokens: 50, timestampMs: 1000, serviceInstance: "start-a"}},
}};
const slots = [
  {{id: 1, is_processing: true, state: "decode", request_id: 101, n_generated_tokens: 30}},
  {{id: 2, is_processing: true, state: "decode", request_id: 102, n_generated_tokens: 70}},
];
process.stdout.write(JSON.stringify(calculateSlotDecodeRates(previous, slots, 3000, "start-a")));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        rates = json.loads(result.stdout)["rates"]
        self.assertEqual(rates, {"1": 5, "2": 10})

    def test_total_kv_cache_usage_is_percent_based_and_rejects_invalid_values(self):
        script = f"""
const {{kvCacheUsage}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify([
  kvCacheUsage(131072, 524288),
  kvCacheUsage(600000, 524288),
  kvCacheUsage(-1, 524288),
  kvCacheUsage(1, 0),
  kvCacheUsage(undefined, 524288),
  kvCacheUsage(1, undefined),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        usage = json.loads(result.stdout)
        self.assertEqual(usage[0], {"used": 131072, "capacity": 524288, "percent": 25})
        self.assertIsNone(usage[1])
        self.assertIsNone(usage[2])
        self.assertIsNone(usage[3])
        self.assertIsNone(usage[4])
        self.assertIsNone(usage[5])

    def test_slot_rate_resets_on_discontinuous_sample(self):
        script = f"""
const {{calculateSlotDecodeRates}} = require({json.dumps(str(APP_JS))});
const previous = {{
  "1": {{requestId: "101", generatedTokens: 20, timestampMs: 1000, serviceInstance: "start-a"}},
}};
const cases = [
  {{timestamp: 3000, instance: "start-a", slot: {{id: 1, is_processing: true, state: "prefill", request_id: 101, n_generated_tokens: 20}}}},
  {{timestamp: 3000, instance: "start-a", slot: {{id: 1, is_processing: true, state: "decode", request_id: 102, n_generated_tokens: 1}}}},
  {{timestamp: 3000, instance: "start-a", slot: {{id: 1, is_processing: true, state: "decode", request_id: 101, n_generated_tokens: 5}}}},
  {{timestamp: 500, instance: "start-a", slot: {{id: 1, is_processing: true, state: "decode", request_id: 101, n_generated_tokens: 25}}}},
  {{timestamp: 3000, instance: "start-b", slot: {{id: 1, is_processing: true, state: "decode", request_id: 101, n_generated_tokens: 25}}}},
];
process.stdout.write(JSON.stringify(cases.map((item) =>
  calculateSlotDecodeRates(previous, [item.slot], item.timestamp, item.instance).rates
)));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout), [{}, {}, {}, {}, {}])

    def test_first_decode_sample_is_sampling(self):
        script = f"""
const {{calculateSlotDecodeRates}} = require({json.dumps(str(APP_JS))});
const slot = {{id: 1, is_processing: true, state: "decode", request_id: 101, n_generated_tokens: 1}};
process.stdout.write(JSON.stringify(calculateSlotDecodeRates({{}}, [slot], 3000, "start-a").rates));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout), {})

    def test_chart_uses_timestamps_and_breaks_gaps(self):
        script = f"""
const {{chartGeometry}} = require({json.dumps(str(APP_JS))});
const geometry = chartGeometry([
  {{timestamp_ms: 2000, decode: 10}},
  {{timestamp_ms: 4000, decode: 20}},
  {{timestamp_ms: 9000, decode: 30}},
], "decode", 100, 100, 30, 0, 10000, 2000);
process.stdout.write(JSON.stringify(geometry));
"""
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        geometry = json.loads(result.stdout)
        self.assertIn("M20.00", geometry["line"])
        self.assertIn("L40.00", geometry["line"])
        self.assertEqual(geometry["line"].count("M"), 2)
        self.assertEqual(geometry["area"].count("Z"), 1)

    def test_chart_tooltip_selects_nearest_real_sample(self):
        script = f"""
const {{nearestHistorySample}} = require({json.dumps(str(APP_JS))});
const samples = [
  {{timestamp_ms: 1000, decode: 10}},
  {{timestamp_ms: 4000, decode: 40}},
  {{timestamp_ms: 10000, decode: 100}},
];
process.stdout.write(JSON.stringify([
  nearestHistorySample(samples, 0),
  nearestHistorySample(samples, 2600),
  nearestHistorySample(samples, 8000),
  nearestHistorySample(samples, 12000),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        selected = json.loads(result.stdout)
        self.assertEqual([item["timestamp_ms"] for item in selected], [1000, 4000, 10000, 10000])

    def test_chinese_translations_do_not_display_prefix_term(self):
        script = f"""
const {{I18N}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(Object.values(I18N["zh-CN"])));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        visible_text = "\n".join(json.loads(result.stdout))
        self.assertNotRegex(visible_text, r"(?i)prefix|前缀")
        self.assertIn("缓存复用", visible_text)

    def test_chart_breaks_when_a_compressed_bucket_is_missing(self):
        script = f"""
const {{chartGeometry}} = require({json.dumps(str(APP_JS))});
const geometry = chartGeometry([
  {{timestamp_ms: 0, decode: 10}},
  {{timestamp_ms: 299999, decode: 20}},
  {{timestamp_ms: 600000, decode: 30}},
  {{timestamp_ms: 899999, decode: 40}},
], "decode", 100, 100, 40, 0, 900000, 300000, true);
process.stdout.write(JSON.stringify(geometry));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout)["line"].count("M"), 2)

    def test_realtime_chart_tolerates_normal_sampling_jitter(self):
        script = f"""
const {{chartGeometry}} = require({json.dumps(str(APP_JS))});
const geometry = chartGeometry([
  {{timestamp_ms: 1999, decode: 10}},
  {{timestamp_ms: 4001, decode: 20}},
], "decode", 100, 100, 20, 0, 6000, 2000);
process.stdout.write(JSON.stringify(geometry));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout)["line"].count("M"), 1)

    def test_history_axes_show_intermediate_time_labels(self):
        script = f"""
const {{historyAxisTicks}} = require({json.dumps(str(APP_JS))});
const start = new Date(2026, 7, 19, 0, 0, 0).getTime();
const end = new Date(2026, 7, 20, 0, 0, 0).getTime();
const data = {{start_ms: start, end_ms: end}};
process.stdout.write(JSON.stringify({{
  day: historyAxisTicks(data, "day"),
  realtime: historyAxisTicks(data, "realtime"),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        labels = json.loads(result.stdout)
        self.assertEqual(
            [tick["label"] for tick in labels["day"]],
            ["00:00", "06:00", "12:00", "18:00", "24:00"],
        )
        self.assertEqual(len(labels["realtime"]), 5)
        self.assertTrue(
            all(tick["label"].count(":") == 2 for tick in labels["realtime"])
        )

    def test_day_axis_uses_real_elapsed_time_across_dst(self):
        script = f"""
const {{historyAxisTicks}} = require({json.dumps(str(APP_JS))});
const start = new Date(2026, 2, 8, 0, 0, 0).getTime();
const end = new Date(2026, 2, 9, 0, 0, 0).getTime();
process.stdout.write(JSON.stringify(historyAxisTicks({{start_ms: start, end_ms: end}}, "day")));
"""
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "TZ": "America/New_York"},
        )
        labels = [tick["label"] for tick in json.loads(result.stdout)]
        self.assertEqual(labels, ["00:00", "06:45", "12:30", "18:15", "24:00"])

    def test_history_delete_range_includes_whole_end_date(self):
        script = f"""
const {{historyDeleteRange}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(historyDeleteRange("2026-03-08", "2026-03-08")));
"""
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "TZ": "America/New_York"},
        )
        values = json.loads(result.stdout)
        self.assertEqual(values["end_ms"] - values["start_ms"], 23 * 60 * 60_000)

    def test_dynamic_rows_do_not_use_inner_html(self):
        self.assertNotIn("innerHTML", APP_JS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

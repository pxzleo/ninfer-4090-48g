import hashlib
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
        self.assertIn('id="request-detail-client-address"', html)
        self.assertIn('id="request-detail-agent-id"', html)
        self.assertIn('aria-labelledby="request-detail-title"', html)
        self.assertIn('row.tabIndex = 0', javascript)
        self.assertIn(
            'keyboardEvent.key === "Enter" || keyboardEvent.key === " "', javascript
        )
        self.assertIn("showRequestDetails", javascript)
        self.assertNotIn('request-detail-content").innerHTML', javascript)
        self.assertIn('$("#request-detail-user-agent").textContent', javascript)

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

    def test_echarts_is_local_and_loaded_before_application(self):
        html = APP_HTML.read_text(encoding="utf-8")
        echarts = APP_HTML.parent / "echarts.min.js"
        license_file = APP_HTML.parent / "ECHARTS-LICENSE.txt"
        notice_file = APP_HTML.parent / "ECHARTS-NOTICE.txt"
        d3_license_file = APP_HTML.parent / "licenses" / "LICENSE-d3.txt"
        zrender_license_file = APP_HTML.parent / "licenses" / "LICENSE-zrender.txt"
        self.assertTrue(echarts.is_file())
        self.assertEqual(
            hashlib.sha256(echarts.read_bytes()).hexdigest(),
            "b66b25aeb4df84e33199dc21694014d336d222cbd9deb0e5a7c14bd6aa0d0fd0",
        )
        self.assertIn("Apache License", license_file.read_text(encoding="utf-8"))
        self.assertIn("Apache ECharts", notice_file.read_text(encoding="utf-8"))
        self.assertIn("Redistribution and use", d3_license_file.read_text(encoding="utf-8"))
        self.assertIn("Baidu Inc.", zrender_license_file.read_text(encoding="utf-8"))
        self.assertIn("Redistribution and use", zrender_license_file.read_text(encoding="utf-8"))
        self.assertLess(
            html.index('/static/echarts.min.js'), html.index('/static/app.js')
        )
        self.assertIn('id="throughput-chart"', html)
        self.assertNotIn('id="chart-window-controls"', html)
        self.assertNotIn('id="history-presets"', html)
        self.assertNotIn('id="chart-zoom-slider"', html)
        self.assertNotIn('id="chart-tooltip"', html)
        javascript = APP_JS.read_text(encoding="utf-8")
        self.assertIn('id: "history-inside"', javascript)
        self.assertNotIn('id: "history-navigator"', javascript)
        self.assertNotIn("xAxisIndex: 1", javascript)
        self.assertNotIn("gridIndex: 1", javascript)

    def test_throughput_series_visual_uses_one_color_for_line_area_and_marker(self):
        script = f"""
const {{throughputSeriesVisual}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(throughputSeriesVisual("#76f0bd")));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "lineStyle": {"color": "#76f0bd", "width": 2},
                "areaStyle": {"color": "#76f0bd", "opacity": 0.065},
                "itemStyle": {"color": "#76f0bd"},
            },
        )

    def test_history_viewport_percentage_round_trips(self):
        script = f"""
const {{historyViewportFromPercent, historyViewportPercent}} = require({json.dumps(str(APP_JS))});
const period = {{start_ms: 1000, end_ms: 11000}};
const viewport = historyViewportFromPercent(period, 25, 75);
process.stdout.write(JSON.stringify({{viewport, percent: historyViewportPercent(period, viewport)}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "viewport": {"start_ms": 3500, "end_ms": 8500},
                "percent": {"start": 25, "end": 75},
            },
        )

    def test_current_history_domain_ends_at_server_available_time(self):
        script = f"""
const {{historyAvailablePeriod}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify([
  historyAvailablePeriod({{start_ms: 1000, end_ms: 11000, available_end_ms: 7000}}),
  historyAvailablePeriod({{start_ms: 1000, end_ms: 11000}}),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                {"start_ms": 1000, "end_ms": 7000},
                {"start_ms": 1000, "end_ms": 11000},
            ],
        )

    def test_calendar_axes_use_the_full_natural_period(self):
        script = f"""
const {{historyAxisPeriod}} = require({json.dumps(str(APP_JS))});
const meta = {{start_ms: 1000, end_ms: 701000, available_end_ms: 101000}};
process.stdout.write(JSON.stringify({{
  day: historyAxisPeriod(meta, "day"),
  week: historyAxisPeriod(meta, "week"),
  month: historyAxisPeriod(meta, "month"),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "day": {"start_ms": 1000, "end_ms": 701000},
                "week": {"start_ms": 1000, "end_ms": 701000},
                "month": {"start_ms": 1000, "end_ms": 701000},
            },
        )

    def test_current_week_chart_zoom_keeps_the_selected_calendar_window(self):
        script = f"""
const {{historyViewportFromChart}} = require({json.dumps(str(APP_JS))});
const meta = {{start_ms: 1000, end_ms: 701000, available_end_ms: 101000}};
process.stdout.write(JSON.stringify(historyViewportFromChart(meta, "week", 0, 50)));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {"start_ms": 1000, "end_ms": 351000},
        )

    def test_current_calendar_zoom_can_expand_beyond_available_data(self):
        script = f"""
const {{historyZoomState}} = require({json.dumps(str(APP_JS))});
const meta = {{
  start_ms: 0,
  end_ms: 24 * 60 * 60 * 1000,
  available_end_ms: 60 * 60 * 1000,
  bucket_ms: 60 * 60 * 1000,
  is_current_period: true,
}};
process.stdout.write(JSON.stringify({{
  atLatest: historyZoomState(meta, "day", {{start_ms: 0, end_ms: 60 * 60 * 1000}}),
  lagged: historyZoomState(meta, "day", {{start_ms: 0, end_ms: 59 * 60 * 1000}}),
  expanded: historyZoomState(meta, "day", {{start_ms: 0, end_ms: 2 * 60 * 60 * 1000}}),
  full: historyZoomState(meta, "day", {{start_ms: 0, end_ms: 24 * 60 * 60 * 1000}}),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "atLatest": {
                    "viewport": {"start_ms": 0, "end_ms": 3_600_000},
                    "followsLatest": True,
                },
                "lagged": {
                    "viewport": {"start_ms": 0, "end_ms": 3_540_000},
                    "followsLatest": False,
                },
                "expanded": {
                    "viewport": {"start_ms": 0, "end_ms": 7_200_000},
                    "followsLatest": False,
                },
                "full": {"viewport": None, "followsLatest": True},
            },
        )

    def test_week_axis_labels_use_weekdays_and_add_time_when_zoomed(self):
        script = f"""
const {{historyAxisTickLabel, setLanguageMode}} = require({json.dumps(str(APP_JS))});
setLanguageMode("zh-CN");
const monday = new Date(2026, 7, 31, 12, 0, 0).getTime();
process.stdout.write(JSON.stringify({{
  full: historyAxisTickLabel("week", 7 * 24 * 60 * 60 * 1000, monday),
  zoomed: historyAxisTickLabel("week", 6 * 60 * 60 * 1000, monday),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        values = json.loads(result.stdout)
        self.assertEqual(values["full"], "周一")
        self.assertRegex(values["zoomed"], r"^周一 \d{2}:\d{2}$")

    def test_day_and_month_axes_use_time_and_date_labels(self):
        script = f"""
const {{historyAxisTickLabel, setLanguageMode}} = require({json.dumps(str(APP_JS))});
setLanguageMode("zh-CN");
const timestamp = new Date(2026, 8, 1, 12, 34, 0).getTime();
process.stdout.write(JSON.stringify({{
  day23: historyAxisTickLabel("day", 23 * 60 * 60 * 1000, timestamp),
  day24: historyAxisTickLabel("day", 24 * 60 * 60 * 1000, timestamp),
  day25: historyAxisTickLabel("day", 25 * 60 * 60 * 1000, timestamp),
  month: historyAxisTickLabel("month", 31 * 24 * 60 * 60 * 1000, timestamp),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {"day23": "12:34", "day24": "12:34", "day25": "12:34", "month": "9/1"},
        )

    def test_latest_history_window_advances_with_available_time(self):
        script = f"""
const {{refreshHistoryViewport}} = require({json.dumps(str(APP_JS))});
const next = {{start_ms: 1000, end_ms: 8000}};
const viewport = {{start_ms: 3000, end_ms: 7000}};
process.stdout.write(JSON.stringify([
  refreshHistoryViewport(next, viewport, true),
  refreshHistoryViewport(next, viewport, false),
  refreshHistoryViewport(next, viewport, true, 6000),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                {"start_ms": 4000, "end_ms": 8000},
                {"start_ms": 3000, "end_ms": 7000},
                {"start_ms": 2000, "end_ms": 6000},
            ],
        )

    def test_history_period_change_and_visible_window_are_deterministic(self):
        script = f"""
const {{historyPeriodChanged}} = require({json.dumps(str(APP_JS))});
const previous = {{period_anchor_ms: 100, start_ms: 0, end_ms: 1000}};
process.stdout.write(JSON.stringify({{
  same: historyPeriodChanged(previous, {{period_anchor_ms: 100, start_ms: 0, end_ms: 1000}}),
  crossed: historyPeriodChanged(previous, {{period_anchor_ms: 200, start_ms: 1000, end_ms: 2000}}),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {"same": False, "crossed": True},
        )

    def test_history_pan_preserves_window_and_stops_at_boundaries(self):
        script = f"""
const {{panHistoryViewport}} = require({json.dumps(str(APP_JS))});
const period = {{start_ms: 0, end_ms: 10000}};
const viewport = {{start_ms: 3000, end_ms: 5000}};
process.stdout.write(JSON.stringify([
  panHistoryViewport(period, viewport, 0.5),
  panHistoryViewport(period, viewport, -10),
  panHistoryViewport(period, viewport, 10),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        values = json.loads(result.stdout)
        self.assertEqual(values[0], {"start_ms": 4000, "end_ms": 6000})
        self.assertEqual(values[1], {"start_ms": 0, "end_ms": 2000})
        self.assertEqual(values[2], {"start_ms": 8000, "end_ms": 10000})

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

    def test_chart_series_inserts_null_when_a_compressed_bucket_is_missing(self):
        script = f"""
const {{historySeriesData}} = require({json.dumps(str(APP_JS))});
const data = historySeriesData([
  {{timestamp_ms: 0, bucket_end_ms: 300000, decode: 10}},
  {{timestamp_ms: 600000, bucket_end_ms: 900000, decode: 30}},
], "decode", 300000, 0, true);
process.stdout.write(JSON.stringify(data));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        self.assertEqual(data[2], [300000, None])

    def test_compressed_chart_gaps_align_to_the_natural_period_start(self):
        script = f"""
const {{historySeriesData}} = require({json.dumps(str(APP_JS))});
const data = historySeriesData([
  {{timestamp_ms: 600, bucket_end_ms: 1600, decode: 10}},
  {{timestamp_ms: 2600, bucket_end_ms: 3600, decode: 20}},
], "decode", 1000, 600, true);
process.stdout.write(JSON.stringify(data));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout), [
                [600, 10, 10, 600],
                [1599, 10, 10, 600],
                [1600, None],
                [2600, 20, 20, 2600],
                [3599, 20, 20, 2600],
            ],
        )

    def test_aggregate_line_keeps_peak_metadata_for_tooltip(self):
        script = f"""
const {{historyAverageSeriesData}} = require({json.dumps(str(APP_JS))});
const samples = [{{
  timestamp_ms: 0, bucket_end_ms: 300000, decode: 10,
  decode_peak: 120, decode_peak_ms: 61000,
}}];
process.stdout.write(JSON.stringify(historyAverageSeriesData(samples, "decode", 300000, 0)));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [[0, 10, 120, 61000], [299999, 10, 120, 61000]],
        )

    def test_realtime_chart_uses_two_second_horizontal_intervals(self):
        script = f"""
const {{historySeriesData}} = require({json.dumps(str(APP_JS))});
const data = historySeriesData([
  {{timestamp_ms: 1999, decode: 10}},
  {{timestamp_ms: 4001, decode: 20}},
], "decode", 2000);
process.stdout.write(JSON.stringify(data));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [[1999, 10], [4000, 10], [4001, 20], [6000, 20]],
        )

    def test_realtime_chart_keeps_collection_gaps_disconnected(self):
        script = f"""
const {{historySeriesData}} = require({json.dumps(str(APP_JS))});
const data = historySeriesData([
  {{timestamp_ms: 0, decode: 10}},
  {{timestamp_ms: 10000, decode: 20}},
], "decode", 2000);
process.stdout.write(JSON.stringify(data));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [[0, 10], [1999, 10], [2000, None], [10000, 20], [11999, 20]],
        )

    def test_realtime_series_uses_stable_timestamp_names_for_animation(self):
        script = f"""
const {{historySeriesData}} = require({json.dumps(str(APP_JS))});
const samples = [
  {{timestamp_ms: 1000, decode: 10}},
  {{timestamp_ms: 3000, decode: 20}},
];
process.stdout.write(JSON.stringify(historySeriesData(samples, "decode", 2000, 0, false, true)));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                {"name": "decode:1000:start", "value": [1000, 10]},
                {"name": "decode:1000:end", "value": [2999, 10]},
                {"name": "decode:3000:start", "value": [3000, 20]},
                {"name": "decode:3000:end", "value": [4999, 20]},
            ],
        )

    def test_realtime_series_keeps_tail_identity_between_refreshes(self):
        script = f"""
const {{historySeriesData}} = require({json.dumps(str(APP_JS))});
const before = historySeriesData([
  {{timestamp_ms: 1000, decode: 10}},
], "decode", 2000, 0, false, true);
const after = historySeriesData([
  {{timestamp_ms: 1000, decode: 10}},
  {{timestamp_ms: 3100, decode: 20}},
], "decode", 2000, 0, false, true);
process.stdout.write(JSON.stringify({{before, after}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["before"][1]["name"], "decode:1000:end")
        self.assertEqual(payload["after"][1]["name"], "decode:1000:end")
        self.assertEqual(payload["before"][1]["value"][0], 2999)
        self.assertEqual(payload["after"][1]["value"][0], 3099)

    def test_tooltip_is_three_compact_lines_and_hides_all_zero_values(self):
        script = f"""
const {{chartTooltip}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify({{
  zero: chartTooltip([
    {{seriesId: "decode", seriesName: "Decode", marker: "●", value: [1000, 0]}},
    {{seriesId: "prefill", seriesName: "Prefill", marker: "●", value: [1000, 0]}},
  ]),
  active: chartTooltip([
    {{seriesId: "decode", seriesName: "Decode", marker: "●", value: [1000, 0, 999, 888]}},
    {{seriesId: "prefill", seriesName: "Prefill", marker: "●", value: [1000, 34, 2047.9, 999]}},
  ]),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["zero"], "")
        self.assertEqual(payload["active"].count("<time"), 1)
        self.assertEqual(payload["active"].count('class="echarts-tooltip-row'), 2)
        self.assertIn('echarts-tooltip-row series-decode', payload["active"])
        self.assertIn('echarts-tooltip-row series-prefill', payload["active"])
        self.assertIn("0 tok/s", payload["active"])
        self.assertIn("34 tok/s", payload["active"])
        self.assertNotIn("2047.9", payload["active"])
        self.assertNotIn("999", payload["active"])

    def test_history_zoom_uses_the_mouse_wheel(self):
        script = f"""
const {{historyInsideZoom}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify(historyInsideZoom({{start: 10, end: 80}})));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "id": "history-inside",
                "type": "inside",
                "xAxisIndex": 0,
                "filterMode": "filter",
                "start": 10,
                "end": 80,
                "minValueSpan": 120_000,
                "zoomOnMouseWheel": True,
                "moveOnMouseMove": True,
                "moveOnMouseWheel": False,
                "preventDefaultMouseMove": False,
            },
        )

    def test_touch_pinch_zoom_runs_at_half_rate(self):
        script = f"""
const {{createHalfSpeedPinchController}} = require({json.dumps(str(APP_JS))});
let enabled = true;
const controller = createHalfSpeedPinchController(() => enabled);
const events = [1.2, 1.3, 1.1, 0.8, 0.7].map(pinchScale => ({{pinchScale}}));
events.forEach(controller.handle);
controller.reset();
const nextGesture = {{pinchScale: 0.8}};
controller.handle(nextGesture);
enabled = false;
const disabled = {{pinchScale: 1.2}};
controller.handle(disabled);
enabled = true;
const reenabled = {{pinchScale: 1.2}};
controller.handle(reenabled);
process.stdout.write(JSON.stringify({{
  consumed: events.map(event => event.__ecRoamConsumed === true),
  nextGesture: nextGesture.__ecRoamConsumed === true,
  disabled: disabled.__ecRoamConsumed === true,
  reenabled: reenabled.__ecRoamConsumed === true,
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "consumed": [False, True, False, False, True],
                "nextGesture": False,
                "disabled": False,
                "reenabled": False,
            },
        )

    def test_realtime_y_axis_ceiling_tracks_the_current_window(self):
        script = f"""
const {{realtimeYAxisCeiling}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify([
  realtimeYAxisCeiling([{{decode: 143.5, prefill: 2047.9}}]),
  realtimeYAxisCeiling([{{decode: 80, prefill: 500}}]),
  realtimeYAxisCeiling([{{decode: 80, prefill: 3000}}]),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(json.loads(result.stdout), [2500, 500, 5000])

    def test_historical_resolution_changes_do_not_animate_between_datasets(self):
        script = f"""
const {{historyAnimationEnabled}} = require({json.dumps(str(APP_JS))});
process.stdout.write(JSON.stringify({{
  realtime: historyAnimationEnabled("realtime"),
  realtimeScaleChange: historyAnimationEnabled("realtime", true),
  day: historyAnimationEnabled("day"),
  week: historyAnimationEnabled("week"),
  month: historyAnimationEnabled("month"),
}}));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "realtime": True,
                "realtimeScaleChange": False,
                "day": False,
                "week": False,
                "month": False,
            },
        )

    def test_preset_window_clamps_to_period_end(self):
        script = f"""
const {{presetHistoryViewport}} = require({json.dumps(str(APP_JS))});
const period = {{start_ms: 1000, end_ms: 11000}};
process.stdout.write(JSON.stringify([
  presetHistoryViewport(period, 4000, 9000),
  presetHistoryViewport(period, 4000, 20000),
  presetHistoryViewport(period, null, 9000),
]));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                {"start_ms": 5000, "end_ms": 9000},
                {"start_ms": 7000, "end_ms": 11000},
                None,
            ],
        )

    def test_preset_window_never_extends_beyond_available_current_period(self):
        script = f"""
const {{presetHistoryViewport}} = require({json.dumps(str(APP_JS))});
const hour = 60 * 60 * 1000;
const period = {{start_ms: 0, end_ms: 24 * hour}};
process.stdout.write(JSON.stringify(
  presetHistoryViewport(period, 12 * hour, 8 * hour)
));
"""
        result = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(result.stdout), {"start_ms": 0, "end_ms": 8 * 60 * 60 * 1000}
        )

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

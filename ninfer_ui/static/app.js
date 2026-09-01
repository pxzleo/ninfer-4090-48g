const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const SNAPSHOT_REFRESH_MS = 2000;
const LOG_REFRESH_MS = 2000;
const LANGUAGE_STORAGE_KEY = "ninfer-ui-language";
const HOUR_MS = 60 * 60_000;
const DAY_MS = 24 * HOUR_MS;
const HISTORY_FOLLOW_TOLERANCE_MS = 1_000;

const I18N = {
  "zh-CN": {
    "nav.main": "主导航", "nav.home": "NInfer Control 首页", "nav.overview": "实时监控", "nav.requests": "请求记录", "nav.settings": "运行配置",
    "language.label": "界面语言", "language.auto": "自动", "language.zh": "中文", "language.en": "English",
    "settings.chineseReasoning": "中文思考",
    "settings.chineseReasoningHelp": "新建会话生效",
    "connection.status": "连接状态", "connection.connecting": "正在连接", "connection.updated": "最后更新", "connection.online": "服务在线", "connection.unavailable": "服务不可用", "connection.failed": "连接失败",
    "action.refresh": "立即刷新", "common.off": "关闭", "common.cancel": "取消", "common.confirm": "确认", "error.network": "网络请求失败，请检查 UI 服务连接",
    "overview.title": "实时运行", "overview.waitingModel": "等待模型信息", "overview.totals": "累计用量",
    "metric.requestsTotal": "累计请求", "metric.outputTotal": "累计输出", "metric.inputTotal": "累计输入", "metric.aggregateDecode": "聚合解码", "metric.waitingThroughput": "等待首个吞吐周期", "metric.prefill": "预填充", "metric.decode": "解码", "metric.runningQueued": "执行 / 排队", "metric.mtpAcceptance": "MTP 接受率", "metric.cumulative": "累计", "metric.cacheHitRate": "缓存命中率",
    "overview.model": "{model} · {context} 上下文 · 视觉能力：{vision}", "common.on": "开", "overview.window": "{seconds} 秒窗口 · {batch} 平均 batch", "overview.noActivity": "当前没有生成活动",
    "trend.title": "吞吐趋势", "trend.defaultWindow": "服务端两秒执行窗口", "trend.range": "吞吐趋势时间范围", "trend.realtime": "实时", "trend.day": "天", "trend.week": "周", "trend.month": "月", "trend.previous": "上一周期", "trend.next": "下一周期", "trend.chart": "吞吐趋势图。历史范围可通过图内缩放调整。", "trend.chartUnavailable": "图表组件加载失败", "trend.realtimeLabel": "最近5分钟 · 2秒采样", "trend.dayLabel": "自然日 · 均值与峰值分离", "trend.weekLabel": "自然周 · 均值与峰值分离", "trend.monthLabel": "自然月 · 均值与峰值分离", "trend.average": "平均", "trend.peak": "峰值", "trend.lastFiveMinutes": "最近5分钟", "trend.previousNamed": "上一{period}", "trend.nextNamed": "下一{period}", "trend.period": "周期", "trend.loadFailed": "吞吐历史读取失败: {message}",
    "slots.title": "执行槽", "slots.description": "执行阶段、上下文占用与推测解码状态", "slots.kvUsage": "总缓存占用", "slots.kvUnavailable": "缓存占用不可用", "slots.idleCached": "空闲 · 缓存已保留", "slots.idle": "空闲", "slots.prefillingProgress": "预填充中 · {progress}%", "slots.decodingRate": "解码中 · {rate} tok/s", "slots.decodingSampling": "解码中 · 采样中", "slots.processing": "处理中", "slots.prefilling": "预填充中", "slots.waiting": "等待调度", "slots.unavailable": "槽状态不可用",
    "gpu.utilization": "利用率", "gpu.memory": "显存", "gpu.power": "功耗", "gpu.clock": "SM 时钟", "gpu.unavailable": "GPU 状态不可用", "lan.title": "局域网连接", "lan.apiAddress": "API 地址", "lan.model": "模型名", "lan.waitingModel": "等待模型信息",
    "requests.title": "最近完成", "requests.refreshLogs": "刷新日志", "requests.request": "请求", "requests.finish": "结束", "requests.input": "输入", "requests.output": "输出", "requests.cacheHit": "缓存命中", "requests.duration": "耗时", "requests.empty": "尚无已完成请求", "requests.rawLogs": "原始服务日志", "requests.autoRefresh": "自动刷新 · 2 秒", "requests.notLoaded": "尚未加载", "requests.loading": "正在读取…", "requests.logEmpty": "日志为空", "requestDetail.kicker": "REQUEST INSPECTOR", "requestDetail.close": "关闭请求详情", "requestDetail.open": "打开请求 #{id} 详情", "requestDetail.completed": "已完成 · {time}", "requestDetail.completedAt": "完成时间", "requestDetail.wallTime": "端到端", "requestDetail.speculative": "推测解码", "requestDetail.rawRecord": "原始完成记录", "requestDetail.rawHint": "用于精确排障与核对", "requestDetail.cachedTokens": "{tokens} tokens 复用", "requestDetail.source": "请求来源", "requestDetail.sourceHint": "由连接地址和可选客户端标识组成", "requestDetail.remoteAddress": "来源地址", "requestDetail.clientId": "客户端标识", "requestDetail.agentId": "Agent 标识", "requestDetail.sessionId": "会话标识", "requestDetail.notProvided": "未提供",
    "settings.title": "运行配置", "settings.configFile": "配置文件", "settings.capacity": "容量与调度", "settings.maxContext": "单请求上下文", "settings.maxContextHelp": "模型原生上限 262144", "settings.kvCapacity": "共享 KV 容量", "settings.kvCapacityHelp": "可填 auto 或 token 数", "settings.maxConcurrency": "最大并发", "settings.maxConcurrencyHelp": "有效范围 1–8", "settings.maxQueue": "排队上限", "settings.maxQueueHelp": "不占用执行槽", "settings.queueTimeout": "排队超时", "settings.milliseconds": "毫秒", "settings.prefillChunk": "预填充分块", "settings.prefillChunkHelp": "128 的倍数", "settings.precision": "精度与生成", "settings.kvType": "KV 类型", "settings.kvTypeHelp": "上下文精度与容量", "settings.specDecode": "推测解码", "settings.specDecodeHelp": "当前模型支持 MTP", "settings.draftHelp": "MTP 有效范围 1–5", "settings.defaultOutput": "默认最大输出", "settings.defaultOutputHelp": "请求未指定时使用", "settings.visionMaxTokens": "视觉总预算", "settings.visionMaxTokensHelp": "单次请求的图片 / 视频 token 总量", "settings.imageTokenBudget": "单张图片预算", "settings.imageTokenBudgetHelp": "0 表示使用模型自身上限", "settings.statsInterval": "统计周期", "settings.statsIntervalHelp": "毫秒，0 表示关闭", "settings.reasoningEffort": "思考等级", "settings.reasoningEffortHelp": "Qwen3.8 默认思考强度", "settings.reasoningOff": "关闭", "settings.reasoningLow": "低", "settings.reasoningMedium": "中", "settings.reasoningHigh": "高", "settings.optimizeDraft": "优化 Draft Head", "settings.vision": "图片 / 视频", "settings.preserveThinking": "保留历史思考", "settings.prefixReuse": "缓存复用", "settings.restore": "恢复当前文件", "settings.save": "保存配置", "settings.saving": "正在保存…", "settings.configUnchanged": "配置没有变化", "settings.applied": "配置已保存；运行中的服务尚未改变", "settings.applyTitle": "保存运行配置", "settings.applyMessage": "保存后会修改 compose.yaml 并生成备份，但不会自动重启正在工作的 NInfer 服务。修改配置后需要重启 NInfer 才能生效。", "settings.applyButton": "保存配置",
    "service.controls": "NInfer 服务控制", "service.start": "启动 NInfer", "service.stop": "停止 NInfer", "service.restart": "重启 NInfer", "service.restarting": "正在重启…", "service.starting": "正在启动…", "service.stopping": "正在停止…", "service.restartTitle": "重启 NInfer", "service.restartMessage": "正在运行的推理请求会中断。UI 将重建容器并等待模型健康检查通过。", "service.restartConfirm": "确认重启", "service.restarted": "NInfer 已重启并通过健康检查", "service.started": "NInfer 已启动并通过健康检查", "service.stopTitle": "停止 NInfer", "service.stopMessage": "正在运行和排队的推理请求都会中断。UI 本身会继续运行，可随时重新启动 NInfer。", "service.stopConfirm": "确认停止", "service.stopped": "NInfer 已停止",
    "history.title": "历史数据管理", "history.retention": "1 分钟级“均值 + 峰值”历史保存在本机 SQLite 数据库中，打开网页、重启 UI 或启停 NInfer 都会继续读取；保留最近 400 天，超过后自动清理。", "history.startDate": "开始日期", "history.endDate": "结束日期", "history.clearRange": "清除日期段数据", "history.invalidDate": "请选择有效日期", "history.endBeforeStart": "结束日期不能早于开始日期", "history.clearTitle": "清除历史数据", "history.clearMessage": "将永久删除 {start} 至 {end}（含首尾日期）的全部吞吐历史，删除后无法恢复。当前日期之后产生的新样本仍会继续记录。", "history.clearConfirm": "确认删除", "history.clearing": "正在清除…", "history.cleared": "已清除 {count} 个长期记录桶",
    "confirm.title": "确认操作", "confirm.enter": "输入", "confirm.continue": "继续",
  },
  en: {
    "nav.main": "Main navigation", "nav.home": "NInfer Control home", "nav.overview": "Live monitoring", "nav.requests": "Request history", "nav.settings": "Runtime settings",
    "language.label": "Language", "language.auto": "Auto", "language.zh": "中文", "language.en": "English",
    "settings.chineseReasoning": "Chinese reasoning",
    "settings.chineseReasoningHelp": "Takes effect for new sessions",
    "connection.status": "Connection status", "connection.connecting": "Connecting", "connection.updated": "Last updated", "connection.online": "Service online", "connection.unavailable": "Service unavailable", "connection.failed": "Connection failed",
    "action.refresh": "Refresh now", "common.off": "Off", "common.cancel": "Cancel", "common.confirm": "Confirm", "error.network": "Network request failed; check the UI service connection",
    "overview.title": "Live workload", "overview.waitingModel": "Waiting for model information", "overview.totals": "Cumulative usage",
    "metric.requestsTotal": "Total requests", "metric.outputTotal": "Total output", "metric.inputTotal": "Total input", "metric.aggregateDecode": "Aggregate decode", "metric.waitingThroughput": "Waiting for the first throughput interval", "metric.prefill": "Prefill", "metric.decode": "Decode", "metric.runningQueued": "Running / queued", "metric.mtpAcceptance": "MTP acceptance", "metric.cumulative": "Cumulative", "metric.cacheHitRate": "Cache hit rate",
    "overview.model": "{model} · {context} context · Vision: {vision}", "common.on": "On", "overview.window": "{seconds}s window · {batch} avg batch", "overview.noActivity": "No generation activity",
    "trend.title": "Throughput trend", "trend.defaultWindow": "Two-second server execution window", "trend.range": "Throughput time range", "trend.realtime": "Live", "trend.day": "Day", "trend.week": "Week", "trend.month": "Month", "trend.previous": "Previous period", "trend.next": "Next period", "trend.chart": "Throughput trend chart. Adjust history with in-chart zoom.", "trend.chartUnavailable": "Chart component failed to load", "trend.realtimeLabel": "Last 5 minutes · 2-second samples", "trend.dayLabel": "Calendar day · separate averages and peaks", "trend.weekLabel": "Calendar week · separate averages and peaks", "trend.monthLabel": "Calendar month · separate averages and peaks", "trend.average": "average", "trend.peak": "peak", "trend.lastFiveMinutes": "Last 5 minutes", "trend.previousNamed": "Previous {period}", "trend.nextNamed": "Next {period}", "trend.period": "period", "trend.loadFailed": "Failed to load throughput history: {message}",
    "slots.title": "Execution slots", "slots.description": "Execution stage, context usage, and speculative decoding state", "slots.kvUsage": "Total KV cache usage", "slots.kvUnavailable": "Cache usage unavailable", "slots.idleCached": "Idle · prefix retained", "slots.idle": "Idle", "slots.prefillingProgress": "Prefilling · {progress}%", "slots.decodingRate": "Decoding · {rate} tok/s", "slots.decodingSampling": "Decoding · sampling", "slots.processing": "Processing", "slots.prefilling": "Prefilling", "slots.waiting": "Waiting for scheduler", "slots.unavailable": "Slot status unavailable",
    "gpu.utilization": "Utilization", "gpu.memory": "VRAM", "gpu.power": "Power", "gpu.clock": "SM clock", "gpu.unavailable": "GPU status unavailable", "lan.title": "LAN connection", "lan.apiAddress": "API address", "lan.model": "Model", "lan.waitingModel": "Waiting for model information",
    "requests.title": "Recently completed", "requests.refreshLogs": "Refresh logs", "requests.request": "Request", "requests.finish": "Finish", "requests.input": "Input", "requests.output": "Output", "requests.cacheHit": "Cache hit", "requests.duration": "Duration", "requests.empty": "No completed requests", "requests.rawLogs": "Raw service logs", "requests.autoRefresh": "Auto-refresh · 2 seconds", "requests.notLoaded": "Not loaded", "requests.loading": "Loading…", "requests.logEmpty": "Log is empty", "requestDetail.kicker": "REQUEST INSPECTOR", "requestDetail.close": "Close request details", "requestDetail.open": "Open details for request #{id}", "requestDetail.completed": "Completed · {time}", "requestDetail.completedAt": "Completed at", "requestDetail.wallTime": "End to end", "requestDetail.speculative": "Speculative decode", "requestDetail.rawRecord": "Raw completion record", "requestDetail.rawHint": "Exact source for diagnostics and verification", "requestDetail.cachedTokens": "{tokens} tokens reused", "requestDetail.source": "Request source", "requestDetail.sourceHint": "Socket peer plus optional client identifiers", "requestDetail.remoteAddress": "Remote address", "requestDetail.clientId": "Client ID", "requestDetail.agentId": "Agent ID", "requestDetail.sessionId": "Session ID", "requestDetail.notProvided": "Not provided",
    "settings.title": "Runtime settings", "settings.configFile": "Config file", "settings.capacity": "Capacity and scheduling", "settings.maxContext": "Per-request context", "settings.maxContextHelp": "Model-native maximum: 262144", "settings.kvCapacity": "Shared KV capacity", "settings.kvCapacityHelp": "Enter auto or a token count", "settings.maxConcurrency": "Maximum concurrency", "settings.maxConcurrencyHelp": "Valid range: 1–8", "settings.maxQueue": "Queue limit", "settings.maxQueueHelp": "Does not occupy execution slots", "settings.queueTimeout": "Queue timeout", "settings.milliseconds": "Milliseconds", "settings.prefillChunk": "Prefill chunk", "settings.prefillChunkHelp": "Must be a multiple of 128", "settings.precision": "Precision and generation", "settings.kvType": "KV type", "settings.kvTypeHelp": "Context precision and capacity", "settings.specDecode": "Speculative decoding", "settings.specDecodeHelp": "The current model supports MTP", "settings.draftHelp": "MTP valid range: 1–5", "settings.defaultOutput": "Default maximum output", "settings.defaultOutputHelp": "Used when the request does not specify one", "settings.visionMaxTokens": "Total vision budget", "settings.visionMaxTokensHelp": "Image and video tokens per request", "settings.imageTokenBudget": "Per-image budget", "settings.imageTokenBudgetHelp": "0 uses the model-native limit", "settings.statsInterval": "Statistics interval", "settings.statsIntervalHelp": "Milliseconds; 0 disables it", "settings.reasoningEffort": "Reasoning level", "settings.reasoningEffortHelp": "Default Qwen3.8 reasoning effort", "settings.reasoningOff": "Off", "settings.reasoningLow": "Low", "settings.reasoningMedium": "Medium", "settings.reasoningHigh": "High", "settings.optimizeDraft": "Optimize Draft Head", "settings.vision": "Image / video", "settings.preserveThinking": "Preserve thinking history", "settings.prefixReuse": "Prefix reuse", "settings.restore": "Restore current file", "settings.save": "Save configuration", "settings.saving": "Saving…", "settings.configUnchanged": "Configuration is unchanged", "settings.applied": "Configuration saved; the running service is unchanged", "settings.applyTitle": "Save runtime configuration", "settings.applyMessage": "Saving modifies compose.yaml and creates a backup, but does not restart the running NInfer service. Restart NInfer for configuration changes to take effect.", "settings.applyButton": "Save configuration",
    "service.controls": "NInfer service controls", "service.start": "Start NInfer", "service.stop": "Stop NInfer", "service.restart": "Restart NInfer", "service.restarting": "Restarting…", "service.starting": "Starting…", "service.stopping": "Stopping…", "service.restartTitle": "Restart NInfer", "service.restartMessage": "Running inference requests will be interrupted. The UI will recreate the container and wait for the model health check.", "service.restartConfirm": "Restart", "service.restarted": "NInfer restarted and passed its health check", "service.started": "NInfer started and passed its health check", "service.stopTitle": "Stop NInfer", "service.stopMessage": "Running and queued inference requests will be interrupted. The UI will remain available so NInfer can be started again.", "service.stopConfirm": "Stop", "service.stopped": "NInfer stopped",
    "history.title": "History management", "history.retention": "One-minute average + peak history is stored in a local SQLite database and remains available after reopening the page, restarting the UI, or stopping and starting NInfer. The latest 400 days are retained; older records are removed automatically.", "history.startDate": "Start date", "history.endDate": "End date", "history.clearRange": "Clear date range", "history.invalidDate": "Select a valid date", "history.endBeforeStart": "The end date cannot be earlier than the start date", "history.clearTitle": "Clear history", "history.clearMessage": "This permanently deletes all throughput history from {start} through {end}, inclusive. This cannot be undone. New samples generated afterward will continue to be recorded.", "history.clearConfirm": "Delete", "history.clearing": "Clearing…", "history.cleared": "Cleared {count} long-term history buckets",
    "confirm.title": "Confirm action", "confirm.enter": "Enter", "confirm.continue": "to continue",
  },
};

function languageFromPreferences(languages) {
  const first = Array.from(languages || []).find(Boolean);
  return String(first || "zh-CN").toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}

function browserStorage() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function browserLocale() {
  if (typeof document === "undefined" || typeof navigator === "undefined") return "zh-CN";
  const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  return languageFromPreferences(languages);
}

function storedLanguageMode() {
  const storage = browserStorage();
  if (!storage) return "auto";
  try {
    const value = storage.getItem(LANGUAGE_STORAGE_KEY);
    return ["auto", "zh-CN", "en"].includes(value) ? value : "auto";
  } catch {
    return "auto";
  }
}

function resolveLocale(mode) {
  return mode === "auto" ? browserLocale() : mode;
}

const state = {
  polling: null,
  logPolling: null,
  logBusy: false,
  activeView: "overview",
  busy: false,
  snapshotRequestId: 0,
  history: [],
  historyRange: "realtime",
  historyAnchorMs: null,
  historyFollowingCurrent: true,
  historyNavigationBusy: false,
  historyMeta: null,
  historyViewport: null,
  historyViewportFollowingLatest: true,
  historyRequestId: 0,
  historyDetailTimer: null,
  slotSamples: {},
  config: null,
  revision: "",
  configSaveBusy: false,
  container: {},
  serviceControlBusy: false,
  serviceAction: null,
  historyClearBusy: false,
  toastTimer: null,
  languageMode: storedLanguageMode(),
  locale: "zh-CN",
  latestSnapshot: null,
  confirmContext: null,
  historyChart: null,
  historyChartSyncing: false,
  realtimeYAxisMax: null,
  selectedRequest: null,
};

state.locale = resolveLocale(state.languageMode);

function t(key, values = {}) {
  const template = I18N[state.locale]?.[key] ?? I18N["zh-CN"][key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? `{${name}}`));
}

function formatLocale() {
  return state.locale === "en" ? "en-US" : "zh-CN";
}

function number(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat(formatLocale(), { maximumFractionDigits: digits }).format(Number(value));
}

function compact(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(formatLocale(), { notation: "compact", maximumFractionDigits: 1 }).format(Number(value));
}

function kvCacheUsage(usedValue, capacityValue) {
  const used = Number(usedValue);
  const capacity = Number(capacityValue);
  if (!Number.isFinite(used) || !Number.isFinite(capacity) || capacity <= 0 || used < 0 || used > capacity) return null;
  return { used, capacity, percent: (used / capacity) * 100 };
}

function slotKvUsage(slot) {
  const used = Number(slot?.n_kv_tokens ?? slot?.n_prompt_tokens);
  const capacity = Number(slot?.n_ctx);
  if (!Number.isFinite(used) || !Number.isFinite(capacity) || capacity <= 0 || used < 0 || used > capacity) return null;
  return { used, capacity, percent: (used / capacity) * 100 };
}

function updateKvCache(metrics) {
  const usage = kvCacheUsage(
    metric(metrics, "ninfer:kv_cache_used_tokens", Number.NaN),
    metric(metrics, "ninfer:kv_cache_capacity_tokens", Number.NaN),
  );
  const meter = $("#kv-cache-meter");
  const fill = $("#kv-cache-meter-fill");
  if (!usage) {
    $("#kv-cache-value").textContent = t("slots.kvUnavailable");
    fill.style.width = "0%";
    meter.removeAttribute("aria-valuenow");
    meter.setAttribute("aria-valuetext", t("slots.kvUnavailable"));
    return;
  }
  const value = `${number(usage.used)} / ${number(usage.capacity)} · ${number(usage.percent, 1)}%`;
  $("#kv-cache-value").textContent = value;
  fill.style.width = `${usage.percent}%`;
  meter.setAttribute("aria-valuenow", usage.percent.toFixed(1));
  meter.setAttribute("aria-valuetext", value);
}

function metric(metrics, name, fallback = 0) {
  const value = metrics?.[name];
  return value === undefined ? fallback : value;
}

function textElement(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = content;
  return element;
}

function localizeApiError(message) {
  if (state.locale !== "en") return message;
  const exact = {
    "Host 格式无效": "Invalid Host header format",
    "确认文本不正确": "Confirmation text is incorrect",
    "NInfer 已经在运行": "NInfer is already running",
    "NInfer 已经停止": "NInfer is already stopped",
    "NInfer 已停止，请使用启动操作": "NInfer is stopped; use the start action",
    "只允许本机修改配置": "Configuration changes are only allowed from this machine",
    "Host 不在本机白名单": "The Host header is not on the local allowlist",
    "Origin 不在本机白名单": "The Origin is not on the local allowlist",
    "必须使用 application/json": "Content-Type must be application/json",
    "请求体大小无效": "Invalid request body size",
    "Content-Length 无效": "Invalid Content-Length header",
    "JSON 无效": "Invalid JSON",
    "JSON 顶层必须是对象": "The top-level JSON value must be an object",
    "页面不存在": "Page not found",
    "接口不存在": "API endpoint not found",
    "路径无效": "Invalid path",
    "结束日期不能早于开始日期": "The end date cannot be earlier than the start date",
    "清理日期格式无效": "Invalid date format",
    "清理日期超出可支持范围": "The date range is outside the supported range",
    "kv_capacity 必须是 auto 或正整数": "kv_capacity must be auto or a positive integer",
    "kv_capacity 不能小于 max_context": "kv_capacity cannot be lower than max_context",
    "kv_capacity 不能超过 max_concurrency × max_context": "kv_capacity cannot exceed max_concurrency × max_context",
    "prefill_chunk 必须是不超过 max_context 的 128 倍数": "prefill_chunk must be a multiple of 128 no greater than max_context",
    "default_max_tokens 必须在 1..max_context 之间": "default_max_tokens must be between 1 and max_context",
    "vision_max_tokens 必须在 1..max_context 之间": "vision_max_tokens must be between 1 and max_context",
    "image_token_budget 必须在 0..vision_max_tokens 之间": "image_token_budget must be between 0 and vision_max_tokens",
    "不支持的 kv_dtype": "Unsupported kv_dtype",
    "spec 只支持 off 或 mtp": "spec only supports off or mtp",
    "关闭 MTP 时不能启用 lm_head_draft": "lm_head_draft cannot be enabled when MTP is off",
    "compose.yaml 中没有 services.ninfer": "compose.yaml does not contain services.ninfer",
    "compose.yaml 中没有 services.ninfer.command": "compose.yaml does not contain services.ninfer.command",
    "ninfer command 必须使用 YAML 列表形式并以 ninfer-serve 开头": "The ninfer command must be a YAML list beginning with ninfer-serve",
    "compose.yaml 已被其他进程修改，请刷新后重试": "compose.yaml was modified by another process; refresh and try again",
    "启动前无法确认容器状态": "Unable to determine container state before starting",
    "Docker Compose 启动失败": "Docker Compose failed to start NInfer",
    "停止前无法确认容器状态": "Unable to determine container state before stopping",
    "Docker Compose 停止失败": "Docker Compose failed to stop NInfer",
    "停止后无法确认容器状态": "Unable to determine container state after stopping",
    "Docker Compose 已返回成功，但 NInfer 容器仍在运行": "Docker Compose returned success, but the NInfer container is still running",
    "重启前无法确认容器状态": "Unable to determine container state before restarting",
    "Docker Compose 重启失败": "Docker Compose failed to restart NInfer",
    "健康检查返回的 JSON 不是对象": "The health check response is not a JSON object",
    "Docker 返回了无效状态": "Docker returned an invalid container state",
    "无法读取 Docker 日志": "Unable to read Docker logs",
  };
  if (exact[message]) return exact[message];
  let match = /^(.+) 必须在 (.+) 之间$/.exec(message);
  if (match) return `${match[1]} must be between ${match[2]}`;
  match = /^(.+) 必须是(整数|布尔值)$/.exec(message);
  if (match) return `${match[1]} must be ${match[2] === "整数" ? "an integer" : "a boolean"}`;
  match = /^(不支持的配置字段|缺少配置字段): (.+)$/.exec(message);
  if (match) return `${match[1] === "不支持的配置字段" ? "Unsupported configuration fields" : "Missing configuration fields"}: ${match[2]}`;
  match = /^无法解析 command token: (.+)$/.exec(message);
  if (match) return `Unable to parse command token: ${match[1]}`;
  match = /^(.+) 在 compose\.yaml 中缺少值$/.exec(message);
  if (match) return `${match[1]} is missing a value in compose.yaml`;
  match = /^容器已启动，但 90 秒内健康检查未通过: (.*)$/.exec(message);
  if (match) return `The container started, but its health check did not pass within 90 seconds: ${match[1]}`;
  return message;
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      cache: "no-store",
      ...options,
      headers: options.body ? { "Content-Type": "application/json", ...(options.headers || {}) } : options.headers,
    });
  } catch (error) {
    throw new Error(t("error.network"), { cause: error });
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = { error: `HTTP ${response.status}` };
  }
  if (!response.ok) throw new Error(localizeApiError(payload.error || `HTTP ${response.status}`));
  return payload;
}

function toast(message, isError = false) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.toggle("error", isError);
  node.classList.add("visible");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => node.classList.remove("visible"), 4200);
}

function setConnection(mode, label) {
  const badge = $("#connection-badge");
  badge.classList.toggle("online", mode === "online");
  badge.classList.toggle("error", mode === "error");
  $("#rail-status").className = `rail-status ${mode}`;
  $("#connection-label").textContent = label;
}

function updateOverview(snapshot) {
  state.latestSnapshot = snapshot;
  const throughput = snapshot.throughput;
  const metrics = snapshot.metrics || {};
  const models = snapshot.models || [];
  const model = models[0];
  const serviceOnline = Boolean(snapshot.service?.online && snapshot.container?.running);
  state.container = snapshot.container || {};
  updateServiceControls(state.container);
  setConnection(serviceOnline ? "online" : "error", t(serviceOnline ? "connection.online" : "connection.unavailable"));
  $("#last-updated").textContent = new Date(snapshot.timestamp_ms).toLocaleTimeString(formatLocale(), { hour12: false });

  if (model) {
    const vision = t(model.modalities?.vision ? "common.on" : "common.off");
    $("#model-line").textContent = t("overview.model", {
      model: model.id,
      context: number(model.context_window),
      vision,
    });
  }

  $("#decode-rate").textContent = throughput ? number(throughput.decode_tokens_per_second, 1) : "0.0";
  $("#prefill-rate").textContent = throughput ? number(throughput.prefill_tokens_per_second, 1) : "0.0";
  $("#active-requests").textContent = number(throughput?.running ?? metric(metrics, "llamacpp:requests_processing"));
  $("#queued-requests").textContent = number(throughput?.waiting ?? metric(metrics, "llamacpp:requests_deferred"));
  $("#decode-context").textContent = throughput
    ? t("overview.window", {
      seconds: number(throughput.interval_seconds, 0),
      batch: number(throughput.average_decode_batch, 2),
    })
    : t("overview.noActivity");
  $("#batch-badge").textContent = `BATCH ${throughput?.average_decode_batch == null ? "—" : number(throughput.average_decode_batch, 2)}`;

  const drafted = metric(metrics, "ninfer:draft_tokens_total");
  const accepted = metric(metrics, "ninfer:draft_accepted_tokens_total");
  const computedPrompt = metric(metrics, "llamacpp:prompt_tokens_total");
  const reusedPrompt = metric(metrics, "ninfer:prefix_cache_hit_tokens_total");
  const cacheTotal = computedPrompt + reusedPrompt;
  $("#mtp-rate").textContent = drafted > 0 ? `${number((accepted / drafted) * 100, 1)}%` : "—";
  $("#cache-rate").textContent = cacheTotal > 0 ? `${number((reusedPrompt / cacheTotal) * 100, 1)}%` : "—";
  $("#cache-tokens").textContent = `${compact(reusedPrompt)} tokens`;
  const requestTotal = number(metric(metrics, "ninfer:requests_total"));
  const outputTotal = compact(metric(metrics, "llamacpp:tokens_predicted_total"));
  const promptTotal = compact(metric(metrics, "llamacpp:prompt_tokens_total"));
  $("#request-total").textContent = requestTotal;
  $("#output-total").textContent = outputTotal;
  $("#prompt-total").textContent = promptTotal;
  $("#overview-request-total").textContent = requestTotal;
  $("#overview-output-total").textContent = outputTotal;
  $("#overview-prompt-total").textContent = promptTotal;
  updateKvCache(metrics);

  updateSlots(
    snapshot.slots || [],
    throughput,
    snapshot.timestamp_ms,
    snapshot.container?.started_at || "",
  );
  updateGpu(snapshot.gpu || {}, snapshot.lan_api_url || snapshot.target, model);
  updateRequests(snapshot.recent_requests || []);
}

function updateServiceControls(container) {
  const running = Boolean(container?.running);
  const error = typeof container?.error === "string" ? container.error : "";
  const unavailable = container?.available === false && !error.includes("No such");
  $("#start-service").disabled = state.serviceControlBusy || running || unavailable;
  $("#stop-service").disabled = state.serviceControlBusy || !running;
  $("#restart-service").disabled = state.serviceControlBusy || !running;
}

function calculateSlotDecodeRates(previousSamples, slots, timestampMs, serviceInstance = "") {
  const rates = {};
  const samples = {};
  const currentTimestamp = Number(timestampMs);
  for (const slot of slots) {
    const slotId = String(slot.id);
    const requestId = String(slot.request_id ?? "");
    const generatedTokens = Number(slot.n_generated_tokens);
    const validSample = slot.is_processing
      && slot.state === "decode"
      && requestId !== ""
      && requestId !== "0"
      && Number.isFinite(currentTimestamp)
      && Number.isInteger(generatedTokens)
      && generatedTokens >= 0;
    if (!validSample) continue;
    const previous = previousSamples[slotId];
    let rate = null;
    if (previous?.requestId === requestId
        && previous?.serviceInstance === serviceInstance
        && currentTimestamp > previous.timestampMs
        && generatedTokens >= previous.generatedTokens) {
      rate = ((generatedTokens - previous.generatedTokens) * 1000)
        / (currentTimestamp - previous.timestampMs);
    }
    samples[slotId] = {
      requestId,
      generatedTokens,
      timestampMs: currentTimestamp,
      serviceInstance,
    };
    if (Number.isFinite(rate)) rates[slotId] = rate;
  }
  return { rates, samples };
}

function slotStage(slot, index, throughput, slotRate = null) {
  const residentKv = Number(slot.n_kv_tokens ?? slot.n_prompt_tokens);
  if (!slot.is_processing) return t(residentKv > 0 ? "slots.idleCached" : "slots.idle");
  if (slot.state === "prefill") {
    const progress = slot.n_prompt_tokens > 0
      ? Math.min(100, Math.max(0, (slot.n_prompt_tokens_processed / slot.n_prompt_tokens) * 100))
      : 0;
    return t("slots.prefillingProgress", { progress: number(progress, 1) });
  }
  if (slot.state === "decode") {
    return Number.isFinite(slotRate)
      ? t("slots.decodingRate", { rate: number(slotRate, 1) })
      : t("slots.decodingSampling");
  }
  if (!throughput) return t("slots.processing");
  const prefilling = Math.max(0, Number(throughput.prefilling) || 0);
  const decoding = Math.max(0, Number(throughput.decode_ready) || 0);
  if (index < prefilling) {
    return t("slots.prefilling");
  }
  if (index < prefilling + decoding) {
    return t("slots.decodingSampling");
  }
  return t("slots.waiting");
}

function updateSlots(slots, throughput, timestampMs, serviceInstance) {
  const host = $("#slot-list");
  host.replaceChildren();
  if (!slots.length) {
    state.slotSamples = {};
    const empty = document.createElement("div");
    empty.className = "empty-state visible";
    empty.textContent = t("slots.unavailable");
    host.append(empty);
    return;
  }
  const slotRates = calculateSlotDecodeRates(
    state.slotSamples,
    slots,
    timestampMs,
    serviceInstance,
  );
  state.slotSamples = slotRates.samples;
  let busyIndex = 0;
  for (const slot of slots) {
    const row = document.createElement("div");
    const stage = slotStage(slot, busyIndex, throughput, slotRates.rates[String(slot.id)]);
    if (slot.is_processing) busyIndex += 1;
    const mode = slot.is_processing ? (stage === t("slots.waiting") ? "waiting" : "busy") : "idle";
    row.className = `slot-row ${mode}`;
    const usage = slotKvUsage(slot) || { used: 0, capacity: Number(slot.n_ctx) || 0, percent: 0 };
    const status = textElement("span", "slot-state", stage);
    status.prepend(document.createElement("i"));
    const depth = textElement("span", "slot-depth", "");
    const depthMeter = document.createElement("i");
    depthMeter.style.width = `${usage.percent}%`;
    depth.append(depthMeter);
    row.append(
      textElement("span", "slot-id", `SLOT ${slot.id}`),
      status,
      depth,
      textElement("span", "slot-tokens", `${number(usage.used)} / ${compact(usage.capacity)}`),
    );
    host.append(row);
  }
}

function lanApiAddress(target, browserHostname) {
  try {
    const address = new URL("/v1", target);
    if (browserHostname) address.hostname = browserHostname;
    return address.toString().replace(/\/$/, "");
  } catch {
    return "—";
  }
}

function updateGpu(gpu, target, model) {
  const browserHostname = typeof window === "undefined" ? "" : window.location.hostname;
  const useBrowserHostname = !target || ["127.0.0.1", "localhost", "::1"].includes(new URL(target).hostname);
  $("#lan-api-address").textContent = lanApiAddress(target, useBrowserHostname ? browserHostname : "");
  $("#lan-model-name").textContent = model?.id || t("lan.waitingModel");
  if (!gpu.available) {
    $("#gpu-name").textContent = gpu.error || t("gpu.unavailable");
    return;
  }
  const memoryPercent = gpu.memory_total_mib > 0 ? (gpu.memory_used_mib / gpu.memory_total_mib) * 100 : 0;
  $("#gpu-name").textContent = gpu.name;
  $("#gpu-util").textContent = number(gpu.utilization);
  $("#gpu-radial").style.setProperty("--value", String(Math.max(0, Math.min(100, gpu.utilization))));
  $("#gpu-temp").textContent = `${number(gpu.temperature_c)}°C`;
  $("#gpu-memory").textContent = `${number(gpu.memory_used_mib / 1024, 1)} / ${number(gpu.memory_total_mib / 1024, 1)} GiB`;
  $("#gpu-memory-meter").style.width = `${memoryPercent}%`;
  $("#gpu-power").textContent = `${number(gpu.power_w, 0)} / ${number(gpu.power_limit_w, 0)} W`;
  $("#gpu-clock").textContent = `${number(gpu.clock_mhz)} MHz`;
}

function requestTimestamp(timestampMs) {
  const timestamp = Number(timestampMs);
  if (!Number.isFinite(timestamp) || timestamp <= 0) return "—";
  return new Intl.DateTimeFormat(formatLocale(), {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).format(new Date(timestamp));
}

function renderRequestDetails(event) {
  if (!event) return;
  const completedAt = requestTimestamp(event.timestamp_ms);
  $("#request-detail-title").textContent = `#${event.id}`;
  $("#request-detail-subtitle").textContent = t("requestDetail.completed", { time: completedAt });
  $("#request-detail-input").textContent = number(event.prompt_tokens);
  $("#request-detail-output").textContent = number(event.completion_tokens);
  $("#request-detail-cache-rate").textContent = `${number(event.cache_hit_rate, 1)}%`;
  $("#request-detail-cache-tokens").textContent = t("requestDetail.cachedTokens", { tokens: number(event.cache_tokens) });
  $("#request-detail-wall").textContent = event.wall || "—";
  $("#request-detail-time").textContent = completedAt;
  $("#request-detail-finish").textContent = event.finish || "—";
  $("#request-detail-ttft").textContent = `${number(event.ttft_ms)} ms`;
  $("#request-detail-prefill").textContent = event.prefill || "—";
  $("#request-detail-decode").textContent = event.decode || "—";
  $("#request-detail-speculative").textContent = String(event.speculative || "—").replace("speculative=", "");
  const missing = t("requestDetail.notProvided");
  const address = event.client_ip
    ? `${event.client_ip.includes(":") ? `[${event.client_ip}]` : event.client_ip}${Number(event.client_port) >= 0 ? `:${event.client_port}` : ""}`
    : missing;
  $("#request-detail-client-address").textContent = address;
  $("#request-detail-client-id").textContent = event.client_id || missing;
  $("#request-detail-agent-id").textContent = event.agent_id || missing;
  $("#request-detail-session-id").textContent = event.session_id || missing;
  $("#request-detail-user-agent").textContent = event.user_agent || missing;
  $("#request-detail-line").textContent = event.line || "—";
}

function showRequestDetails(event) {
  state.selectedRequest = event;
  renderRequestDetails(event);
  const dialog = $("#request-detail-dialog");
  if (!dialog.open) dialog.showModal();
  $(".request-detail-close").focus();
}

function updateRequests(events) {
  const body = $("#request-table-body");
  body.replaceChildren();
  $("#request-empty").classList.toggle("visible", events.length === 0);
  for (const event of events) {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-label", t("requestDetail.open", { id: event.id }));
    const values = [
      `#${event.id}`,
      event.finish,
      number(event.prompt_tokens),
      number(event.completion_tokens),
      `${number(event.cache_hit_rate, 1)}%`,
      `${number(event.ttft_ms)} ms`,
      event.decode,
      event.wall,
      event.speculative.replace("speculative=", ""),
    ];
    row.append(...values.map(value => textElement("td", "", value)));
    row.addEventListener("click", () => showRequestDetails(event));
    row.addEventListener("keydown", keyboardEvent => {
      if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
        keyboardEvent.preventDefault();
        showRequestDetails(event);
      }
    });
    body.append(row);
  }
}

function clampHistoryViewport(period, viewport) {
  const periodStart = Number(period?.start_ms);
  const periodEnd = Number(period?.end_ms);
  if (!Number.isFinite(periodStart) || !Number.isFinite(periodEnd) || periodEnd <= periodStart) {
    return null;
  }
  const total = periodEnd - periodStart;
  let start = Number(viewport?.start_ms);
  let end = Number(viewport?.end_ms);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return { start_ms: periodStart, end_ms: periodEnd };
  }
  const duration = Math.max(1, Math.min(total, end - start));
  start = Math.max(periodStart, Math.min(periodEnd - duration, start));
  return { start_ms: start, end_ms: start + duration };
}

function panHistoryViewport(period, viewport, ratio) {
  const current = clampHistoryViewport(period, viewport);
  if (!current) return null;
  const duration = current.end_ms - current.start_ms;
  const offset = duration * (Number(ratio) || 0);
  return clampHistoryViewport(period, {
    start_ms: current.start_ms + offset,
    end_ms: current.end_ms + offset,
  });
}

function historyPeriodChanged(previous, next) {
  if (!previous || !next) return false;
  if (previous.period_anchor_ms != null && next.period_anchor_ms != null) {
    return String(previous.period_anchor_ms) !== String(next.period_anchor_ms);
  }
  return Number(previous.start_ms) !== Number(next.start_ms)
    || Number(previous.end_ms) !== Number(next.end_ms);
}

function historyAvailablePeriod(period) {
  const start = Number(period?.start_ms);
  const calendarEnd = Number(period?.end_ms);
  const reportedEnd = Number(period?.available_end_ms ?? calendarEnd);
  if (!Number.isFinite(start) || !Number.isFinite(calendarEnd) || calendarEnd <= start) {
    return null;
  }
  const end = Math.max(start, Math.min(calendarEnd, reportedEnd));
  return { start_ms: start, end_ms: end > start ? end : Math.min(calendarEnd, start + 1) };
}

function historyAxisPeriod(period, range) {
  const available = historyAvailablePeriod(period);
  if (!available || !["day", "week", "month"].includes(range)) return available;
  return { start_ms: Number(period.start_ms), end_ms: Number(period.end_ms) };
}

function historyViewportFromChart(period, range, start, end) {
  return historyViewportFromPercent(historyAxisPeriod(period, range), start, end);
}

function historyDetailViewport(period, viewport) {
  const available = historyAvailablePeriod(period);
  if (!available || !viewport) return null;
  const start = Math.max(available.start_ms, Number(viewport.start_ms));
  const end = Math.min(available.end_ms, Number(viewport.end_ms));
  return Number.isFinite(start) && Number.isFinite(end) && end > start
    ? { start_ms: start, end_ms: end }
    : null;
}


function historyWindowLabel(range) {
  return t({
    realtime: "trend.realtimeLabel",
    day: "trend.dayLabel",
    week: "trend.weekLabel",
    month: "trend.monthLabel",
  }[range] || "trend.defaultWindow");
}

function historyAnimationEnabled(range, scaleChanged = false) {
  return range === "realtime" && !scaleChanged;
}

function historyPeriodLabel(data, range) {
  if (range === "realtime") return t("trend.lastFiveMinutes");
  const start = new Date(Number(data.start_ms));
  const end = new Date(Number(data.end_ms) - 1);
  if (range === "day") {
    return new Intl.DateTimeFormat(formatLocale(), {
      year: "numeric", month: state.locale === "en" ? "short" : "long", day: "numeric",
    }).format(start);
  }
  if (range === "week") {
    const options = { year: "numeric", month: "short", day: "numeric" };
    const formatter = new Intl.DateTimeFormat(formatLocale(), options);
    return `${formatter.format(start)} – ${formatter.format(end)}`;
  }
  return new Intl.DateTimeFormat(formatLocale(), {
    year: "numeric", month: "long",
  }).format(start);
}

function chartTimestamp(timestampMs, seconds = false) {
  return new Intl.DateTimeFormat(formatLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: seconds ? "2-digit" : undefined,
    hourCycle: "h23",
  }).format(new Date(timestampMs));
}

function historyChartWindow() {
  if (!state.historyMeta) return null;
  if (state.historyRange === "realtime") {
    return {
      start_ms: Number(state.historyMeta.start_ms),
      end_ms: Number(state.historyMeta.end_ms),
    };
  }
  return clampHistoryViewport(
    historyAxisPeriod(state.historyMeta, state.historyRange), state.historyViewport,
  );
}

function historyAxisWindow() {
  if (!state.historyMeta) return null;
  const axisPeriod = historyAxisPeriod(state.historyMeta, state.historyRange);
  if (state.historyRange === "week" && state.historyViewport === null) return axisPeriod;
  return clampHistoryViewport(axisPeriod, historyChartWindow());
}


function historyViewportPercent(period, viewport) {
  const current = clampHistoryViewport(period, viewport);
  if (!current) return { start: 0, end: 100 };
  const startMs = Number(period.start_ms);
  const duration = Number(period.end_ms) - startMs;
  return {
    start: ((current.start_ms - startMs) / duration) * 100,
    end: ((current.end_ms - startMs) / duration) * 100,
  };
}

function historyViewportFromPercent(period, start, end) {
  const periodStart = Number(period?.start_ms);
  const duration = Number(period?.end_ms) - periodStart;
  if (!Number.isFinite(duration) || duration <= 0) return null;
  const low = Math.max(0, Math.min(100, Number(start) || 0));
  const high = Math.max(low, Math.min(100, Number(end) || 0));
  return clampHistoryViewport(period, {
    start_ms: periodStart + duration * low / 100,
    end_ms: periodStart + duration * high / 100,
  });
}

function presetHistoryViewport(period, durationMs, referenceMs) {
  if (!period || durationMs == null) return null;
  const periodStart = Number(period.start_ms);
  const periodEnd = Number(period.end_ms);
  const referenceEnd = Math.max(periodStart, Math.min(periodEnd, Number(referenceMs)));
  const end = referenceEnd > periodStart ? referenceEnd : Math.min(periodEnd, periodStart + 1);
  const availableDuration = end - periodStart;
  const duration = Math.min(Number(durationMs), availableDuration);
  return { start_ms: end - duration, end_ms: end };
}

function refreshHistoryViewport(period, viewport, followingLatest, referenceMs = period?.end_ms) {
  if (!viewport) return null;
  const duration = Number(viewport.end_ms) - Number(viewport.start_ms);
  if (followingLatest) {
    return presetHistoryViewport(period, duration, referenceMs);
  }
  return clampHistoryViewport(period, viewport);
}

function historyViewportFollowsReference(viewport, referenceMs, toleranceMs = 0) {
  return Boolean(viewport)
    && Math.abs(Number(viewport.end_ms) - Number(referenceMs)) <= Math.max(1, Number(toleranceMs) || 0);
}

function historyZoomState(period, range, viewport) {
  const axisPeriod = historyAxisPeriod(period, range);
  const current = clampHistoryViewport(axisPeriod, viewport);
  if (!axisPeriod || !current) return { viewport: null, followsLatest: false };
  const periodDuration = axisPeriod.end_ms - axisPeriod.start_ms;
  const viewportDuration = current.end_ms - current.start_ms;
  const selected = viewportDuration >= periodDuration - 1 ? null : current;
  const referenceMs = historyAvailablePeriod(period)?.end_ms;
  return {
    viewport: selected,
    followsLatest: Boolean(
      period?.is_current_period
        && (selected === null
          || historyViewportFollowsReference(
            current, referenceMs, HISTORY_FOLLOW_TOLERANCE_MS,
          ))
    ),
  };
}

function historySeriesData(
  samples, key, bucketMs, periodStartMs = 0, compressed = false, stableNames = false,
) {
  if (compressed) return historyAverageSeriesData(samples, key, bucketMs, periodStartMs);
  const result = [];
  const point = (timestamp, value, role, sampleTimestamp = timestamp) => stableNames
    ? { name: `${key}:${sampleTimestamp}:${role}`, value: [timestamp, value] }
    : [timestamp, value];
  for (let index = 0; index < samples.length; index += 1) {
    const sample = samples[index];
    const timestamp = Number(sample.timestamp_ms);
    if (!Number.isFinite(timestamp)) continue;
    const nextTimestamp = Number(samples[index + 1]?.timestamp_ms);
    const continuous = Number.isFinite(nextTimestamp)
      && nextTimestamp > timestamp
      && nextTimestamp - timestamp <= bucketMs * 1.75;
    const end = continuous ? nextTimestamp : timestamp + bucketMs;
    const value = Math.max(0, Number(sample[key]) || 0);
    result.push(
      point(timestamp, value, "start", timestamp),
      point(end - 1, value, "end", timestamp),
    );
    if (!continuous && index + 1 < samples.length) {
      result.push(point(end, null, "gap", timestamp));
    }
  }
  return result;
}

function realtimeYAxisCeiling(samples) {
  let observed = 0;
  for (const sample of samples) {
    observed = Math.max(
      observed,
      Math.max(0, Number(sample.decode) || 0),
      Math.max(0, Number(sample.prefill) || 0),
    );
  }
  const exponent = 10 ** Math.floor(Math.log10(Math.max(1, observed)));
  const normalized = observed / exponent;
  const step = [1, 2, 2.5, 5, 10].find(candidate => normalized <= candidate) || 10;
  return step * exponent;
}

function throughputSeriesVisual(color) {
  return {
    lineStyle: { color, width: 2 },
    areaStyle: { color, opacity: .065 },
    itemStyle: { color },
  };
}

function historyAverageSeriesData(samples, key, bucketMs, periodStartMs = 0) {
  const result = [];
  let previousEnd = null;
  const peakKey = `${key}_peak`;
  const peakTimestampKey = `${key}_peak_ms`;
  for (const sample of samples) {
    const start = Number(sample.timestamp_ms);
    const end = Number(sample.bucket_end_ms);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) continue;
    if (previousEnd !== null && start > previousEnd) result.push([previousEnd, null]);
    const value = Math.max(0, Number(sample[key]) || 0);
    const peak = Math.max(value, Number(sample[peakKey]) || 0);
    const peakTimestamp = Number(sample[peakTimestampKey]) || start;
    result.push(
      [start, value, peak, peakTimestamp],
      [end - 1, value, peak, peakTimestamp],
    );
    previousEnd = end;
  }
  return result;
}

function localDateStart(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) throw new Error(t("history.invalidDate"));
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(0);
  date.setHours(0, 0, 0, 0);
  date.setFullYear(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    throw new Error(t("history.invalidDate"));
  }
  return date;
}

function historyDeleteRange(startValue, endValue) {
  const start = localDateStart(startValue);
  const end = localDateStart(endValue);
  if (end < start) throw new Error(t("history.endBeforeStart"));
  end.setDate(end.getDate() + 1);
  return { start_ms: start.getTime(), end_ms: end.getTime() };
}

function historyReferenceMs() {
  if (!state.historyMeta) return Date.now();
  return Number(historyAvailablePeriod(state.historyMeta)?.end_ms ?? Date.now());
}

function scheduleHistoryDetailLoad() {
  if (state.historyDetailTimer !== null) clearTimeout(state.historyDetailTimer);
  state.historyDetailTimer = setTimeout(() => {
    state.historyDetailTimer = null;
    loadHistory();
  }, 180);
}

function syncViewportFromChart() {
  if (state.historyChartSyncing || !state.historyChart || !state.historyMeta || state.historyRange === "realtime") return;
  const zoom = state.historyChart.getOption().dataZoom?.find(item => item.id === "history-inside");
  if (!zoom) return;
  const viewport = historyViewportFromChart(state.historyMeta, state.historyRange, zoom.start, zoom.end);
  const zoomState = historyZoomState(state.historyMeta, state.historyRange, viewport);
  state.historyViewport = zoomState.viewport;
  state.historyViewportFollowingLatest = zoomState.followsLatest;
  scheduleHistoryDetailLoad();
}

function historyAxisTickLabel(range, duration, timestamp) {
  if (range === "realtime") {
    return new Intl.DateTimeFormat(formatLocale(), {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    }).format(new Date(timestamp));
  }
  if (range === "week") {
    const weekday = new Intl.DateTimeFormat(formatLocale(), { weekday: "short" })
      .format(new Date(timestamp));
    if (duration > 2 * DAY_MS) return weekday;
    const clock = new Intl.DateTimeFormat(formatLocale(), {
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).format(new Date(timestamp));
    return `${weekday} ${clock}`;
  }
  if (duration <= 2 * DAY_MS) {
    return new Intl.DateTimeFormat(formatLocale(), {
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).format(new Date(timestamp));
  }
  return new Intl.DateTimeFormat(formatLocale(), { month: "numeric", day: "numeric" }).format(new Date(timestamp));
}

function chartAxisLabel(timestamp) {
  const viewport = historyAxisWindow();
  const duration = viewport ? viewport.end_ms - viewport.start_ms : 0;
  return historyAxisTickLabel(state.historyRange, duration, timestamp);
}

function chartTooltip(params) {
  const points = params.filter(item => Array.isArray(item.value) && item.value[1] != null);
  if (!points.length) return "";
  const pointBySeries = new Map(points.map(item => [item.seriesId, item]));
  const metricValue = item => {
    const value = Number(item?.value?.[1]);
    return Number.isFinite(value) ? Math.max(0, value) : null;
  };
  const decode = pointBySeries.get("decode");
  const prefill = pointBySeries.get("prefill");
  const decodeValue = metricValue(decode);
  const prefillValue = metricValue(prefill);
  if (!(decodeValue > 0 || prefillValue > 0)) return "";
  const row = (item, key, label, value) => {
    const displayValue = value === null ? "—" : `${number(value, 1)} tok/s`;
    return `<div class="echarts-tooltip-row series-${key}"><span>${item?.marker || ""}${label}</span><strong>${displayValue}</strong></div>`;
  };
  const rows = [
    row(decode, "decode", t("metric.decode"), decodeValue),
    row(prefill, "prefill", t("metric.prefill"), prefillValue),
  ].join("");
  return `<time>${chartTimestamp(Number(points[0].value[0]), true)}</time>${rows}`;
}

function historyInsideZoom(percent) {
  return {
    id: "history-inside", type: "inside", xAxisIndex: 0, filterMode: "filter",
    start: percent.start, end: percent.end, minValueSpan: 2 * 60_000,
    zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false,
    preventDefaultMouseMove: false,
  };
}

function createHalfSpeedPinchController(isEnabled) {
  let lastDirection = 0;
  let consumeNext = false;
  const reset = () => {
    lastDirection = 0;
    consumeNext = false;
  };
  const handle = event => {
    if (!isEnabled()) {
      reset();
      return;
    }
    const direction = event.pinchScale > 1 ? 1 : event.pinchScale < 1 ? -1 : 0;
    if (!direction) return;
    if (direction !== lastDirection) {
      lastDirection = direction;
      consumeNext = false;
    }
    // ECharts 6.1 applies a fixed 1.1 step per pinch event and checks this
    // marker before zooming. Preserve the first event, then consume alternate
    // events so continuous touch zoom runs at roughly half its native rate.
    if (consumeNext) event.__ecRoamConsumed = true;
    consumeNext = !consumeNext;
  };
  return { handle, reset };
}

function initializeHistoryChart() {
  const container = $("#throughput-chart");
  if (!window.echarts) {
    $("#chart-library-error").hidden = false;
    container.hidden = true;
    return;
  }
  state.historyChart = window.echarts.init(container, null, { renderer: "canvas" });
  const pinchController = createHalfSpeedPinchController(
    () => state.historyRange !== "realtime",
  );
  state.historyChart.getZr().on("pinch", pinchController.handle);
  ["touchstart", "touchend", "touchcancel"].forEach(eventName => {
    container.addEventListener(eventName, pinchController.reset, { passive: true });
  });
  state.historyChart.on("datazoom", syncViewportFromChart);
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => state.historyChart?.resize());
    observer.observe(container);
  } else {
    window.addEventListener("resize", () => state.historyChart?.resize());
  }
}

async function loadHistory(reportError = false) {
  const requestedRange = state.historyRange;
  const requestId = ++state.historyRequestId;
  try {
    const params = new URLSearchParams({ range: requestedRange });
    if (requestedRange !== "realtime" && !state.historyFollowingCurrent && state.historyAnchorMs) {
      params.set("anchor_ms", String(state.historyAnchorMs));
    }
    const detailViewport = requestedRange === "realtime"
      ? null
      : historyDetailViewport(state.historyMeta, state.historyViewport);
    if (detailViewport) {
      params.set("detail_start_ms", String(Math.floor(detailViewport.start_ms)));
      params.set("detail_end_ms", String(Math.ceil(detailViewport.end_ms)));
    }
    const data = await api(`/api/history?${params}`);
    if (requestId !== state.historyRequestId || requestedRange !== state.historyRange) return;
    const crossedPeriodBoundary = requestedRange !== "realtime"
      && historyPeriodChanged(state.historyMeta, data);
    state.history = data.samples || [];
    state.historyMeta = data;
    if (crossedPeriodBoundary || data.detail_reset) {
      state.historyViewport = null;
      state.historyViewportFollowingLatest = Boolean(data.is_current_period);
    } else if (requestedRange !== "realtime" && state.historyViewport) {
      state.historyViewport = refreshHistoryViewport(
        historyAxisPeriod(data, requestedRange),
        state.historyViewport,
        state.historyViewportFollowingLatest && Boolean(data.is_current_period),
        historyAvailablePeriod(data).end_ms,
      );
    }
    state.historyAnchorMs = data.period_anchor_ms;
    state.historyFollowingCurrent = Boolean(data.is_current_period);
    $("#trend-window-label").textContent = historyWindowLabel(requestedRange);
    $("#period-nav").hidden = requestedRange === "realtime";
    $("#history-period-label").textContent = historyPeriodLabel(data, requestedRange);
    const periodName = t({ day: "trend.day", week: "trend.week", month: "trend.month" }[requestedRange] || "trend.period");
    const previousLabel = t("trend.previousNamed", { period: periodName });
    const nextLabel = t("trend.nextNamed", { period: periodName });
    $("#history-prev").setAttribute("aria-label", previousLabel);
    $("#history-prev").title = previousLabel;
    $("#history-next").setAttribute("aria-label", nextLabel);
    $("#history-next").title = nextLabel;
    drawChart();
  } catch (error) {
    if (requestId !== state.historyRequestId) return;
    if (reportError) toast(error.message, true);
    else console.warn(t("trend.loadFailed", { message: error.message }));
  } finally {
    if (requestId === state.historyRequestId) {
      state.historyNavigationBusy = false;
      $("#history-prev").disabled = false;
      $("#history-next").disabled = Boolean(state.historyMeta?.is_current_period);
    }
  }
}

function setHistoryRange(range) {
  state.historyRange = range;
  state.historyAnchorMs = null;
  state.historyFollowingCurrent = true;
  state.historyNavigationBusy = false;
  state.history = [];
  state.historyMeta = null;
  state.historyViewport = null;
  state.historyViewportFollowingLatest = true;
  if (range === "realtime") state.realtimeYAxisMax = null;
  $("#period-nav").hidden = range === "realtime";
  $$("[data-history-range]").forEach(button => {
    const active = button.dataset.historyRange === range;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  drawChart();
  loadHistory(true);
}

function shiftHistoryPeriod(direction) {
  if (state.historyRange === "realtime" || !state.historyMeta || state.historyNavigationBusy) return;
  if (direction > 0 && state.historyMeta.is_current_period) return;
  state.historyNavigationBusy = true;
  $("#history-prev").disabled = true;
  $("#history-next").disabled = true;
  state.historyFollowingCurrent = false;
  state.historyViewport = null;
  state.historyViewportFollowingLatest = false;
  state.historyAnchorMs = direction < 0
    ? state.historyMeta.start_ms - 1
    : state.historyMeta.end_ms;
  state.history = [];
  drawChart();
  loadHistory(true);
}

function drawChart() {
  if (!state.historyChart) return;
  const fallbackEnd = Date.now();
  const availablePeriod = historyAvailablePeriod(state.historyMeta) || {
    start_ms: fallbackEnd - 5 * 60_000, end_ms: fallbackEnd,
  };
  const historical = state.historyRange !== "realtime" && Boolean(state.historyMeta);
  const axisPeriod = historyAxisPeriod(state.historyMeta, state.historyRange) || availablePeriod;
  const periodStart = axisPeriod.start_ms;
  const periodEnd = axisPeriod.end_ms;
  const viewport = historyAxisWindow() || axisPeriod;
  const percent = historyViewportPercent(axisPeriod, viewport);
  const sampleBucketMs = state.historyMeta?.sample_bucket_ms ?? state.historyMeta?.bucket_ms ?? 2_000;
  const compressed = state.historyMeta?.compression === "average_peak_envelope";
  let realtimeScaleChanged = false;
  if (state.historyRange === "realtime") {
    const nextYAxisMax = realtimeYAxisCeiling(state.history);
    realtimeScaleChanged = state.realtimeYAxisMax !== null
      && nextYAxisMax !== state.realtimeYAxisMax;
    state.realtimeYAxisMax = nextYAxisMax;
  }
  const animationEnabled = historyAnimationEnabled(state.historyRange, realtimeScaleChanged);
  const zoom = historical ? [historyInsideZoom(percent)] : [];
  const seriesDefinitions = [
    { name: t("metric.decode"), key: "decode", color: "#76f0bd" },
    { name: t("metric.prefill"), key: "prefill", color: "#65a9ff" },
  ];
  const averageSeries = seriesDefinitions.map(item => ({
    id: item.key,
    name: item.name,
    type: "line",
    data: historySeriesData(
      state.history, item.key, sampleBucketMs, periodStart, compressed,
      state.historyRange === "realtime",
    ),
    showSymbol: false,
    symbol: "none",
    connectNulls: false,
    ...throughputSeriesVisual(item.color),
    emphasis: { disabled: true },
  }));
  const mainGrid = { left: 0, right: 0, top: 12, bottom: 28, containLabel: false };
  const mainXAxis = {
    type: "time", min: periodStart, max: periodEnd, boundaryGap: false,
    axisLine: { lineStyle: { color: "#25302b" } }, axisTick: { show: false },
    axisLabel: { color: "#738078", fontSize: 9, hideOverlap: true, formatter: chartAxisLabel },
    splitLine: { show: false },
  };
  const mainYAxis = {
    type: "value", min: 0,
    ...(state.historyRange === "realtime" ? { max: state.realtimeYAxisMax } : {}),
    splitNumber: 4,
    axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false },
    splitLine: { lineStyle: { color: "rgba(255,255,255,.055)", width: 1 } },
  };
  state.historyChartSyncing = true;
  state.historyChart.setOption({
    animation: animationEnabled,
    animationDuration: animationEnabled ? 260 : 0,
    animationDurationUpdate: animationEnabled ? 220 : 0,
    aria: { enabled: true, description: t("trend.chart") },
    grid: [mainGrid],
    tooltip: {
      trigger: "axis", confine: true, transitionDuration: .12,
      className: "throughput-tooltip",
      backgroundColor: "rgba(12,17,15,.96)", borderColor: "#304039", borderWidth: 1,
      padding: [6, 8], textStyle: { color: "#d4ded9", fontSize: 10 },
      extraCssText: "pointer-events:none;",
      axisPointer: { type: "line", lineStyle: { color: "rgba(206,222,214,.34)", width: 1 } },
      formatter: chartTooltip,
    },
    xAxis: [mainXAxis],
    yAxis: [mainYAxis],
    dataZoom: zoom,
    series: averageSeries,
  }, { notMerge: true, lazyUpdate: false });
  state.historyChartSyncing = false;
}

async function refreshSnapshot(force = false) {
  if (state.busy && !force) return;
  const requestId = ++state.snapshotRequestId;
  state.busy = true;
  $("#refresh-button").classList.add("loading");
  try {
    const snapshot = await api("/api/snapshot");
    if (requestId !== state.snapshotRequestId) return;
    updateOverview(snapshot);
    loadHistory();
    if (snapshot.errors?.length) console.warn(...snapshot.errors);
  } catch (error) {
    if (requestId !== state.snapshotRequestId) return;
    setConnection("error", t("connection.failed"));
    if (force) toast(error.message, true);
  } finally {
    if (requestId === state.snapshotRequestId) {
      state.busy = false;
      $("#refresh-button").classList.remove("loading");
    }
  }
}

function showView(name) {
  state.activeView = name;
  $$(".nav-item").forEach(item => item.classList.toggle("is-active", item.dataset.view === name));
  $$(".view").forEach(view => view.classList.toggle("is-active", view.id === `view-${name}`));
  syncLogPolling();
  if (name === "settings" && !state.config) loadConfig();
}

async function loadRawLogs(showLoading = false) {
  if (state.logBusy) return;
  state.logBusy = true;
  const output = $("#raw-log-output");
  if (showLoading) output.textContent = t("requests.loading");
  try {
    const data = await api("/api/logs?tail=180");
    output.textContent = data.lines.join("\n") || t("requests.logEmpty");
    output.scrollTop = output.scrollHeight;
  } catch (error) {
    output.textContent = error.message;
    toast(error.message, true);
  } finally {
    state.logBusy = false;
  }
}

function stopLogPolling() {
  clearInterval(state.logPolling);
  state.logPolling = null;
}

function syncLogPolling() {
  const shouldPoll = state.activeView === "requests" && $("#raw-log-details").open;
  stopLogPolling();
  if (!shouldPoll) return;
  loadRawLogs(true);
  state.logPolling = setInterval(loadRawLogs, LOG_REFRESH_MS);
}

const CONFIG_NUMBER_FIELDS = new Set([
  "max_context", "max_concurrency", "max_pending_requests", "pending_timeout_ms",
  "prefill_chunk", "draft_tokens", "log_stats_interval_ms", "default_max_tokens",
  "vision_max_tokens", "image_token_budget",
]);
const CONFIG_BOOL_FIELDS = new Set([
  "lm_head_draft", "vision", "preserve_thinking", "chinese_reasoning", "prefix_reuse", "cuda_graph",
]);

function populateConfig(config) {
  const form = $("#settings-form");
  for (const [name, value] of Object.entries(config)) {
    const field = form.elements.namedItem(name);
    if (!field) continue;
    if (CONFIG_BOOL_FIELDS.has(name)) field.checked = Boolean(value);
    else field.value = value;
  }
  syncSpecFields();
  syncReasoningFields();
  syncVisionFields();
}

function configFromForm() {
  const form = $("#settings-form");
  const config = {};
  for (const name of Object.keys(state.config || {})) {
    const field = form.elements.namedItem(name);
    if (!field) continue;
    if (CONFIG_BOOL_FIELDS.has(name)) config[name] = field.checked;
    else if (CONFIG_NUMBER_FIELDS.has(name)) config[name] = Number(field.value);
    else config[name] = field.value.trim();
  }
  return config;
}

async function loadConfig() {
  try {
    const data = await api("/api/config");
    state.config = data.config;
    state.revision = data.revision;
    populateConfig(data.config);
    $("#compose-path").textContent = data.compose_path;
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveConfig(event) {
  event.preventDefault();
  const action = configApplyConfirmationOptions();
  const confirmed = await confirmAction(action);
  if (!confirmed) return;
  state.configSaveBusy = true;
  const button = $("#save-config");
  button.disabled = true;
  button.textContent = t("settings.saving");
  try {
    const data = await api("/api/config/apply", {
      method: "POST",
      body: JSON.stringify({
        config: configFromForm(),
        revision: state.revision,
        confirmation: action.confirmation,
      }),
    });
    toast(t(data.changed ? "settings.applied" : "settings.configUnchanged"));
    await loadConfig();
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.configSaveBusy = false;
    button.disabled = false;
    button.textContent = t("settings.save");
  }
}

function syncSpecFields() {
  const form = $("#settings-form");
  const off = form.elements.spec.value === "off";
  form.elements.draft_tokens.disabled = off;
  form.elements.lm_head_draft.disabled = off;
  if (off) form.elements.lm_head_draft.checked = false;
}

function syncReasoningFields() {
  const form = $("#settings-form");
  const off = form.elements.reasoning_effort.value === "none";
  form.elements.chinese_reasoning.disabled = off;
  if (off) form.elements.chinese_reasoning.checked = false;
}

function syncVisionFields() {
  const form = $("#settings-form");
  const off = !form.elements.vision.checked;
  form.elements.vision_max_tokens.disabled = off;
  form.elements.image_token_budget.disabled = off;
}

function confirmationState(phrase = "") {
  const phraseRequired = Boolean(phrase);
  return {
    phraseRequired,
    inputHidden: !phraseRequired,
    confirmDisabled: phraseRequired,
  };
}

function serviceConfirmationOptions(action) {
  if (action === "restart") {
    return {
      titleKey: "service.restartTitle",
      messageKey: "service.restartMessage",
      buttonKey: "service.restartConfirm",
      confirmation: "RESTART NINFER",
    };
  }
  if (action === "stop") {
    return {
      titleKey: "service.stopTitle",
      messageKey: "service.stopMessage",
      buttonKey: "service.stopConfirm",
      confirmation: "STOP NINFER",
    };
  }
  throw new Error(`Unsupported service confirmation action: ${action}`);
}

function configApplyConfirmationOptions() {
  return {
    titleKey: "settings.applyTitle",
    messageKey: "settings.applyMessage",
    buttonKey: "settings.applyButton",
    confirmation: "APPLY CONFIG",
  };
}

function renderConfirmContext() {
  const context = state.confirmContext;
  if (!context) return;
  const presentation = confirmationState(context.phrase);
  $("#confirm-title").textContent = t(context.titleKey, context.values);
  $("#confirm-message").textContent = t(context.messageKey, context.values);
  $("#confirm-phrase").textContent = context.phrase;
  $("#confirm-phrase-row").hidden = presentation.inputHidden;
  $("#confirm-submit").textContent = t(context.buttonKey);
}

function confirmAction({
  titleKey, messageKey, phrase = "", buttonKey = "common.confirm", values = {},
}) {
  const dialog = $("#confirm-dialog");
  dialog.returnValue = "";
  state.confirmContext = { titleKey, messageKey, phrase, buttonKey, values };
  renderConfirmContext();
  if (state.selectedRequest && $("#request-detail-dialog").open) {
    renderRequestDetails(state.selectedRequest);
  }
  $("#confirm-input").value = "";
  $("#confirm-submit").disabled = confirmationState(phrase).confirmDisabled;
  dialog.showModal();
  (phrase ? $("#confirm-input") : $("#confirm-submit")).focus();
  return new Promise(resolve => {
    const onClose = () => {
      dialog.removeEventListener("close", onClose);
      const confirmed = dialog.returnValue === "confirm" &&
        (!phrase || $("#confirm-input").value === phrase);
      state.confirmContext = null;
      resolve(confirmed);
    };
    dialog.addEventListener("close", onClose);
  });
}

async function restartService() {
  const action = serviceConfirmationOptions("restart");
  const confirmed = await confirmAction(action);
  if (!confirmed) return;
  state.serviceControlBusy = true;
  state.serviceAction = "restart";
  updateServiceControls(state.container);
  const button = $("#restart-service");
  button.textContent = t("service.restarting");
  try {
    await api("/api/restart", {
      method: "POST",
      body: JSON.stringify({ confirmation: action.confirmation }),
    });
    toast(t("service.restarted"));
    await refreshSnapshot(true);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.textContent = t("service.restart");
    state.serviceAction = null;
    state.serviceControlBusy = false;
    updateServiceControls(state.container);
  }
}

async function startService() {
  state.serviceControlBusy = true;
  state.serviceAction = "start";
  updateServiceControls(state.container);
  const button = $("#start-service");
  button.textContent = t("service.starting");
  try {
    await api("/api/start", {
      method: "POST",
      body: JSON.stringify({ confirmation: "START NINFER" }),
    });
    toast(t("service.started"));
    await refreshSnapshot(true);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.textContent = t("service.start");
    state.serviceAction = null;
    state.serviceControlBusy = false;
    updateServiceControls(state.container);
  }
}

async function stopService() {
  const action = serviceConfirmationOptions("stop");
  const confirmed = await confirmAction(action);
  if (!confirmed) return;
  state.serviceControlBusy = true;
  state.serviceAction = "stop";
  updateServiceControls(state.container);
  const button = $("#stop-service");
  button.textContent = t("service.stopping");
  try {
    await api("/api/stop", {
      method: "POST",
      body: JSON.stringify({ confirmation: action.confirmation }),
    });
    toast(t("service.stopped"));
    await refreshSnapshot(true);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.textContent = t("service.stop");
    state.serviceAction = null;
    state.serviceControlBusy = false;
    updateServiceControls(state.container);
  }
}

async function clearHistory() {
  const startValue = $("#history-delete-start").value;
  const endValue = $("#history-delete-end").value;
  let range;
  try {
    range = historyDeleteRange(startValue, endValue);
  } catch (error) {
    toast(error.message, true);
    return;
  }
  const confirmed = await confirmAction({
    titleKey: "history.clearTitle",
    messageKey: "history.clearMessage",
    values: { start: startValue, end: endValue },
    phrase: "DELETE HISTORY",
    buttonKey: "history.clearConfirm",
  });
  if (!confirmed) return;
  const button = $("#clear-history");
  button.disabled = true;
  state.historyClearBusy = true;
  button.textContent = t("history.clearing");
  try {
    const data = await api("/api/history/clear", {
      method: "POST",
      body: JSON.stringify({
        start_date: startValue,
        end_date: endValue,
        confirmation: "DELETE HISTORY",
      }),
    });
    const deleted = data.deleted || {};
    toast(t("history.cleared", { count: number(deleted.aggregate_rows) }));
    state.history = [];
    state.historyMeta = null;
    await loadHistory(true);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    state.historyClearBusy = false;
    button.textContent = t("history.clearRange");
  }
}

function initializeHistoryDeleteRange() {
  const now = new Date();
  const today = [
    String(now.getFullYear()).padStart(4, "0"),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
  const start = $("#history-delete-start");
  const end = $("#history-delete-end");
  start.value = today;
  end.value = today;
}

function applyTranslations() {
  document.documentElement.lang = state.locale;
  document.title = "NInfer Control";
  $$('[data-i18n]').forEach(node => {
    node.textContent = t(node.dataset.i18n);
  });
  $$('[data-i18n-aria]').forEach(node => {
    node.setAttribute("aria-label", t(node.dataset.i18nAria));
  });
  $$('[data-i18n-title]').forEach(node => {
    node.title = t(node.dataset.i18nTitle);
  });
  $("#language-select").value = state.languageMode;

  if (state.latestSnapshot) {
    state.slotSamples = {};
    updateOverview(state.latestSnapshot);
  }
  if (state.historyMeta) {
    $("#trend-window-label").textContent = historyWindowLabel(state.historyRange);
    $("#history-period-label").textContent = historyPeriodLabel(state.historyMeta, state.historyRange);
    drawChart();
  }
  if (state.configSaveBusy) $("#save-config").textContent = t("settings.saving");
  if (state.serviceAction) {
    const progressKey = {
      start: "service.starting",
      stop: "service.stopping",
      restart: "service.restarting",
    }[state.serviceAction];
    $(`#${state.serviceAction}-service`).textContent = t(progressKey);
  }
  if (state.historyClearBusy) $("#clear-history").textContent = t("history.clearing");
  renderConfirmContext();
  if ($("#raw-log-details").open) loadRawLogs(true);
}

function setLanguageMode(mode) {
  if (!["auto", "zh-CN", "en"].includes(mode)) return;
  state.languageMode = mode;
  state.locale = resolveLocale(mode);
  const storage = browserStorage();
  if (storage) {
    try {
      storage.setItem(LANGUAGE_STORAGE_KEY, mode);
    } catch {
      // The selection still applies for this page when browser storage is unavailable.
    }
  }
  if (typeof document !== "undefined") applyTranslations();
}

function bindEvents() {
  $("#language-select").addEventListener("change", event => setLanguageMode(event.target.value));
  $$(".nav-item").forEach(item => item.addEventListener("click", () => showView(item.dataset.view)));
  $("#refresh-button").addEventListener("click", () => refreshSnapshot(true));
  $("#reload-logs").addEventListener("click", () => loadRawLogs(true));
  $("#raw-log-details").addEventListener("toggle", syncLogPolling);
  $("#settings-form").addEventListener("submit", saveConfig);
  $("#reset-config").addEventListener("click", loadConfig);
  $("#start-service").addEventListener("click", startService);
  $("#stop-service").addEventListener("click", stopService);
  $("#restart-service").addEventListener("click", restartService);
  $("#clear-history").addEventListener("click", clearHistory);
  $("#history-delete-start").addEventListener("change", event => {
    const end = $("#history-delete-end");
    if (end.value < event.target.value) end.value = event.target.value;
  });
  $$("[data-history-range]").forEach(button => {
    button.addEventListener("click", () => setHistoryRange(button.dataset.historyRange));
  });
  $("#history-prev").addEventListener("click", () => shiftHistoryPeriod(-1));
  $("#history-next").addEventListener("click", () => shiftHistoryPeriod(1));
  $("#settings-form").elements.spec.addEventListener("change", syncSpecFields);
  $("#settings-form").elements.reasoning_effort.addEventListener("change", syncReasoningFields);
  $("#settings-form").elements.vision.addEventListener("change", syncVisionFields);
  $("#confirm-input").addEventListener("input", event => {
    $("#confirm-submit").disabled = event.target.value !== $("#confirm-phrase").textContent;
  });
}

function init() {
  initializeHistoryChart();
  initializeHistoryDeleteRange();
  applyTranslations();
  bindEvents();
  refreshSnapshot(true);
  state.polling = setInterval(refreshSnapshot, SNAPSHOT_REFRESH_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refreshSnapshot(true);
      syncLogPolling();
    } else {
      stopLogPolling();
    }
  });
  window.addEventListener("languagechange", () => {
    if (state.languageMode === "auto") setLanguageMode("auto");
  });
}

if (typeof document !== "undefined") init();

if (typeof module !== "undefined") {
  module.exports = {
    I18N,
    calculateSlotDecodeRates,
    clampHistoryViewport,
    configApplyConfirmationOptions,
    confirmationState,
    historyAnimationEnabled,
    historyAverageSeriesData,
    historyAxisPeriod,
    historyAxisTickLabel,
    historyAvailablePeriod,
    historyDetailViewport,
    historyDeleteRange,
    historyPeriodChanged,
    historySeriesData,
    historyViewportFromPercent,
    historyViewportFromChart,
    historyViewportFollowsReference,
    historyViewportPercent,
    historyZoomState,
    kvCacheUsage,
    lanApiAddress,
    languageFromPreferences,
    localizeApiError,
    panHistoryViewport,
    presetHistoryViewport,
    refreshHistoryViewport,
    realtimeYAxisCeiling,
    resolveLocale,
    serviceConfirmationOptions,
    setLanguageMode,
    slotKvUsage,
    slotStage,
    t,
    chartTooltip,
    createHalfSpeedPinchController,
    historyInsideZoom,
    throughputSeriesVisual,
  };
}

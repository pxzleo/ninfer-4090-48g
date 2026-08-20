const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const SNAPSHOT_REFRESH_MS = 2000;
const LOG_REFRESH_MS = 2000;
const LANGUAGE_STORAGE_KEY = "ninfer-ui-language";

const I18N = {
  "zh-CN": {
    "nav.main": "主导航", "nav.home": "NInfer Control 首页", "nav.overview": "实时监控", "nav.requests": "请求记录", "nav.settings": "运行配置",
    "language.label": "界面语言", "language.auto": "自动", "language.zh": "中文", "language.en": "English",
    "connection.status": "连接状态", "connection.connecting": "正在连接", "connection.updated": "最后更新", "connection.online": "服务在线", "connection.unavailable": "服务不可用", "connection.failed": "连接失败",
    "action.refresh": "立即刷新", "common.off": "关闭", "common.cancel": "取消", "common.confirm": "确认", "error.network": "网络请求失败，请检查 UI 服务连接",
    "overview.title": "实时运行", "overview.waitingModel": "等待模型信息", "overview.totals": "累计用量",
    "metric.requestsTotal": "累计请求", "metric.outputTotal": "累计输出", "metric.inputTotal": "累计输入", "metric.aggregateDecode": "聚合解码", "metric.waitingThroughput": "等待首个吞吐周期", "metric.prefill": "预填充", "metric.decode": "解码", "metric.runningQueued": "执行 / 排队", "metric.mtpAcceptance": "MTP 接受率", "metric.cumulative": "累计", "metric.cacheHitRate": "缓存命中率",
    "overview.model": "{model} · {context} 上下文 · 视觉能力：{vision}", "common.on": "开", "overview.window": "{seconds} 秒窗口 · {batch} 平均 batch", "overview.noActivity": "当前没有生成活动",
    "trend.title": "吞吐趋势", "trend.defaultWindow": "服务端两秒执行窗口", "trend.range": "吞吐趋势时间范围", "trend.realtime": "实时", "trend.day": "天", "trend.week": "周", "trend.month": "月", "trend.previous": "上一周期", "trend.next": "下一周期", "trend.chart": "吞吐趋势图", "trend.realtimeLabel": "最近5分钟 · 2秒采样", "trend.dayLabel": "自然日 · 5分钟峰值保真", "trend.weekLabel": "自然周 · 30分钟峰值保真", "trend.monthLabel": "自然月 · 2小时峰值保真", "trend.lastFiveMinutes": "最近5分钟", "trend.previousNamed": "上一{period}", "trend.nextNamed": "下一{period}", "trend.period": "周期", "trend.loadFailed": "吞吐历史读取失败: {message}",
    "slots.title": "执行槽", "slots.description": "执行阶段、上下文占用与推测解码状态", "slots.kvUsage": "总缓存占用", "slots.kvUnavailable": "缓存占用不可用", "slots.idleCached": "空闲 · 缓存已保留", "slots.idle": "空闲", "slots.prefillingProgress": "预填充中 · {progress}%", "slots.decodingRate": "解码中 · {rate} tok/s", "slots.decodingSampling": "解码中 · 采样中", "slots.processing": "处理中", "slots.prefilling": "预填充中", "slots.waiting": "等待调度", "slots.unavailable": "槽状态不可用",
    "gpu.utilization": "利用率", "gpu.memory": "显存", "gpu.power": "功耗", "gpu.clock": "SM 时钟", "gpu.unavailable": "GPU 状态不可用", "lan.title": "局域网连接", "lan.apiAddress": "API 地址", "lan.model": "模型名", "lan.waitingModel": "等待模型信息",
    "requests.title": "最近完成", "requests.refreshLogs": "刷新日志", "requests.request": "请求", "requests.finish": "结束", "requests.input": "输入", "requests.output": "输出", "requests.cacheHit": "缓存命中", "requests.duration": "耗时", "requests.empty": "尚无已完成请求", "requests.rawLogs": "原始服务日志", "requests.autoRefresh": "自动刷新 · 2 秒", "requests.notLoaded": "尚未加载", "requests.loading": "正在读取…", "requests.logEmpty": "日志为空",
    "settings.title": "运行配置", "settings.configFile": "配置文件", "settings.capacity": "容量与调度", "settings.maxContext": "单请求上下文", "settings.maxContextHelp": "模型原生上限 262144", "settings.kvCapacity": "共享 KV 容量", "settings.kvCapacityHelp": "可填 auto 或 token 数", "settings.maxConcurrency": "最大并发", "settings.maxConcurrencyHelp": "有效范围 1–8", "settings.maxQueue": "排队上限", "settings.maxQueueHelp": "不占用执行槽", "settings.queueTimeout": "排队超时", "settings.milliseconds": "毫秒", "settings.prefillChunk": "预填充分块", "settings.prefillChunkHelp": "128 的倍数", "settings.precision": "精度与生成", "settings.kvType": "KV 类型", "settings.kvTypeHelp": "上下文精度与容量", "settings.specDecode": "推测解码", "settings.specDecodeHelp": "当前模型支持 MTP", "settings.draftHelp": "MTP 有效范围 1–5", "settings.defaultOutput": "默认最大输出", "settings.defaultOutputHelp": "请求未指定时使用", "settings.statsInterval": "统计周期", "settings.statsIntervalHelp": "毫秒，0 表示关闭", "settings.reasoningEffort": "思考等级", "settings.reasoningEffortHelp": "Qwen3.8 默认思考强度", "settings.reasoningOff": "关闭", "settings.reasoningLow": "低", "settings.reasoningMedium": "中", "settings.reasoningHigh": "高", "settings.optimizeDraft": "优化 Draft Head", "settings.vision": "图片 / 视频", "settings.preserveThinking": "保留历史思考", "settings.prefixReuse": "缓存复用", "settings.restore": "恢复当前文件", "settings.preview": "预览变更", "settings.changePreview": "变更预览", "settings.noAutoRestart": "修改配置需写入 compose.yaml 并重启后生效", "settings.previewHint": "调整参数后点击“预览变更”", "settings.writeCompose": "写入 compose.yaml", "settings.noChanges": "没有变更", "settings.previewReady": "预览已生成，运行服务尚未改变", "settings.configUnchanged": "配置没有变化", "settings.applied": "配置已写入；运行中的服务尚未改变", "settings.applyTitle": "写入启动配置", "settings.applyMessage": "这会修改 compose.yaml 并生成备份，但不会重启正在工作的 NInfer 服务。", "settings.applyButton": "写入配置",
    "service.controls": "NInfer 服务控制", "service.start": "启动 NInfer", "service.stop": "停止 NInfer", "service.restart": "重启 NInfer", "service.restarting": "正在重启…", "service.starting": "正在启动…", "service.stopping": "正在停止…", "service.restartTitle": "重启 NInfer", "service.restartMessage": "正在运行的推理请求会中断。UI 将重建容器并等待模型健康检查通过。", "service.restartConfirm": "确认重启", "service.restarted": "NInfer 已重启并通过健康检查", "service.started": "NInfer 已启动并通过健康检查", "service.stopTitle": "停止 NInfer", "service.stopMessage": "正在运行和排队的推理请求都会中断。UI 本身会继续运行，可随时重新启动 NInfer。", "service.stopConfirm": "确认停止", "service.stopped": "NInfer 已停止",
    "history.title": "历史数据管理", "history.retention": "5 分钟级“均值 + 峰值”历史保存在本机 SQLite 数据库中，打开网页、重启 UI 或启停 NInfer 都会继续读取；保留最近 400 天，超过后自动清理。", "history.startDate": "开始日期", "history.endDate": "结束日期", "history.clearRange": "清除日期段数据", "history.invalidDate": "请选择有效日期", "history.endBeforeStart": "结束日期不能早于开始日期", "history.clearTitle": "清除历史数据", "history.clearMessage": "将永久删除 {start} 至 {end}（含首尾日期）的全部吞吐历史，删除后无法恢复。当前日期之后产生的新样本仍会继续记录。", "history.clearConfirm": "确认删除", "history.clearing": "正在清除…", "history.cleared": "已清除 {count} 个长期记录桶",
    "confirm.title": "确认操作", "confirm.enter": "输入", "confirm.continue": "继续",
  },
  en: {
    "nav.main": "Main navigation", "nav.home": "NInfer Control home", "nav.overview": "Live monitoring", "nav.requests": "Request history", "nav.settings": "Runtime settings",
    "language.label": "Language", "language.auto": "Auto", "language.zh": "中文", "language.en": "English",
    "connection.status": "Connection status", "connection.connecting": "Connecting", "connection.updated": "Last updated", "connection.online": "Service online", "connection.unavailable": "Service unavailable", "connection.failed": "Connection failed",
    "action.refresh": "Refresh now", "common.off": "Off", "common.cancel": "Cancel", "common.confirm": "Confirm", "error.network": "Network request failed; check the UI service connection",
    "overview.title": "Live workload", "overview.waitingModel": "Waiting for model information", "overview.totals": "Cumulative usage",
    "metric.requestsTotal": "Total requests", "metric.outputTotal": "Total output", "metric.inputTotal": "Total input", "metric.aggregateDecode": "Aggregate decode", "metric.waitingThroughput": "Waiting for the first throughput interval", "metric.prefill": "Prefill", "metric.decode": "Decode", "metric.runningQueued": "Running / queued", "metric.mtpAcceptance": "MTP acceptance", "metric.cumulative": "Cumulative", "metric.cacheHitRate": "Cache hit rate",
    "overview.model": "{model} · {context} context · Vision: {vision}", "common.on": "On", "overview.window": "{seconds}s window · {batch} avg batch", "overview.noActivity": "No generation activity",
    "trend.title": "Throughput trend", "trend.defaultWindow": "Two-second server execution window", "trend.range": "Throughput time range", "trend.realtime": "Live", "trend.day": "Day", "trend.week": "Week", "trend.month": "Month", "trend.previous": "Previous period", "trend.next": "Next period", "trend.chart": "Throughput trend chart", "trend.realtimeLabel": "Last 5 minutes · 2-second samples", "trend.dayLabel": "Calendar day · 5-minute peak-preserving", "trend.weekLabel": "Calendar week · 30-minute peak-preserving", "trend.monthLabel": "Calendar month · 2-hour peak-preserving", "trend.lastFiveMinutes": "Last 5 minutes", "trend.previousNamed": "Previous {period}", "trend.nextNamed": "Next {period}", "trend.period": "period", "trend.loadFailed": "Failed to load throughput history: {message}",
    "slots.title": "Execution slots", "slots.description": "Execution stage, context usage, and speculative decoding state", "slots.kvUsage": "Total KV cache usage", "slots.kvUnavailable": "Cache usage unavailable", "slots.idleCached": "Idle · prefix retained", "slots.idle": "Idle", "slots.prefillingProgress": "Prefilling · {progress}%", "slots.decodingRate": "Decoding · {rate} tok/s", "slots.decodingSampling": "Decoding · sampling", "slots.processing": "Processing", "slots.prefilling": "Prefilling", "slots.waiting": "Waiting for scheduler", "slots.unavailable": "Slot status unavailable",
    "gpu.utilization": "Utilization", "gpu.memory": "VRAM", "gpu.power": "Power", "gpu.clock": "SM clock", "gpu.unavailable": "GPU status unavailable", "lan.title": "LAN connection", "lan.apiAddress": "API address", "lan.model": "Model", "lan.waitingModel": "Waiting for model information",
    "requests.title": "Recently completed", "requests.refreshLogs": "Refresh logs", "requests.request": "Request", "requests.finish": "Finish", "requests.input": "Input", "requests.output": "Output", "requests.cacheHit": "Cache hit", "requests.duration": "Duration", "requests.empty": "No completed requests", "requests.rawLogs": "Raw service logs", "requests.autoRefresh": "Auto-refresh · 2 seconds", "requests.notLoaded": "Not loaded", "requests.loading": "Loading…", "requests.logEmpty": "Log is empty",
    "settings.title": "Runtime settings", "settings.configFile": "Config file", "settings.capacity": "Capacity and scheduling", "settings.maxContext": "Per-request context", "settings.maxContextHelp": "Model-native maximum: 262144", "settings.kvCapacity": "Shared KV capacity", "settings.kvCapacityHelp": "Enter auto or a token count", "settings.maxConcurrency": "Maximum concurrency", "settings.maxConcurrencyHelp": "Valid range: 1–8", "settings.maxQueue": "Queue limit", "settings.maxQueueHelp": "Does not occupy execution slots", "settings.queueTimeout": "Queue timeout", "settings.milliseconds": "Milliseconds", "settings.prefillChunk": "Prefill chunk", "settings.prefillChunkHelp": "Must be a multiple of 128", "settings.precision": "Precision and generation", "settings.kvType": "KV type", "settings.kvTypeHelp": "Context precision and capacity", "settings.specDecode": "Speculative decoding", "settings.specDecodeHelp": "The current model supports MTP", "settings.draftHelp": "MTP valid range: 1–5", "settings.defaultOutput": "Default maximum output", "settings.defaultOutputHelp": "Used when the request does not specify one", "settings.statsInterval": "Statistics interval", "settings.statsIntervalHelp": "Milliseconds; 0 disables it", "settings.reasoningEffort": "Reasoning level", "settings.reasoningEffortHelp": "Default Qwen3.8 reasoning effort", "settings.reasoningOff": "Off", "settings.reasoningLow": "Low", "settings.reasoningMedium": "Medium", "settings.reasoningHigh": "High", "settings.optimizeDraft": "Optimize Draft Head", "settings.vision": "Image / video", "settings.preserveThinking": "Preserve thinking history", "settings.prefixReuse": "Prefix reuse", "settings.restore": "Restore current file", "settings.preview": "Preview changes", "settings.changePreview": "Change preview", "settings.noAutoRestart": "Configuration changes take effect after writing compose.yaml and restarting", "settings.previewHint": "Adjust parameters, then select “Preview changes”", "settings.writeCompose": "Write compose.yaml", "settings.noChanges": "No changes", "settings.previewReady": "Preview ready; the running service is unchanged", "settings.configUnchanged": "Configuration is unchanged", "settings.applied": "Configuration written; the running service is unchanged", "settings.applyTitle": "Write startup configuration", "settings.applyMessage": "This modifies compose.yaml and creates a backup, but does not restart the running NInfer service.", "settings.applyButton": "Write configuration",
    "service.controls": "NInfer service controls", "service.start": "Start NInfer", "service.stop": "Stop NInfer", "service.restart": "Restart NInfer", "service.restarting": "Restarting…", "service.starting": "Starting…", "service.stopping": "Stopping…", "service.restartTitle": "Restart NInfer", "service.restartMessage": "Running inference requests will be interrupted. The UI will recreate the container and wait for the model health check.", "service.restartConfirm": "Restart", "service.restarted": "NInfer restarted and passed its health check", "service.started": "NInfer started and passed its health check", "service.stopTitle": "Stop NInfer", "service.stopMessage": "Running and queued inference requests will be interrupted. The UI will remain available so NInfer can be started again.", "service.stopConfirm": "Stop", "service.stopped": "NInfer stopped",
    "history.title": "History management", "history.retention": "Five-minute average + peak history is stored in a local SQLite database and remains available after reopening the page, restarting the UI, or stopping and starting NInfer. The latest 400 days are retained; older records are removed automatically.", "history.startDate": "Start date", "history.endDate": "End date", "history.clearRange": "Clear date range", "history.invalidDate": "Select a valid date", "history.endBeforeStart": "The end date cannot be earlier than the start date", "history.clearTitle": "Clear history", "history.clearMessage": "This permanently deletes all throughput history from {start} through {end}, inclusive. This cannot be undone. New samples generated afterward will continue to be recorded.", "history.clearConfirm": "Delete", "history.clearing": "Clearing…", "history.cleared": "Cleared {count} long-term history buckets",
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
  historyRequestId: 0,
  slotSamples: {},
  config: null,
  revision: "",
  preview: null,
  container: {},
  serviceControlBusy: false,
  serviceAction: null,
  historyClearBusy: false,
  toastTimer: null,
  languageMode: storedLanguageMode(),
  locale: "zh-CN",
  latestSnapshot: null,
  confirmContext: null,
  chartHoverSample: null,
  chartHoverRatio: null,
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

function updateRequests(events) {
  const body = $("#request-table-body");
  body.replaceChildren();
  $("#request-empty").classList.toggle("visible", events.length === 0);
  for (const event of events) {
    const row = document.createElement("tr");
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
    body.append(row);
  }
}

function chartGeometry(
  samples, key, width, height, maxValue, startMs, endMs, bucketMs, compressed = false,
) {
  const duration = Math.max(1, endMs - startMs);
  const segments = [];
  let segment = [];
  let previousTimestamp = null;
  let previousBucket = null;
  for (const sample of samples) {
    const timestamp = Number(sample.timestamp_ms);
    if (!Number.isFinite(timestamp) || timestamp < startMs || timestamp > endMs) continue;
    const bucket = Math.floor((timestamp - startMs) / bucketMs);
    const missingData = compressed
      ? previousBucket !== null && bucket > previousBucket + 1
      : previousTimestamp !== null && timestamp - previousTimestamp > bucketMs * 1.75;
    if (missingData) {
      if (segment.length) segments.push(segment);
      segment = [];
    }
    const x = ((timestamp - startMs) / duration) * width;
    const y = height - (Math.max(0, Number(sample[key]) || 0) / maxValue) * (height - 10) - 5;
    segment.push({ x, y });
    previousTimestamp = timestamp;
    previousBucket = bucket;
  }
  if (segment.length) segments.push(segment);
  const line = segments.map(points => {
    if (points.length === 1) {
      const point = points[0];
      return `M${Math.max(0, point.x - 1).toFixed(2)},${point.y.toFixed(2)} L${Math.min(width, point.x + 1).toFixed(2)},${point.y.toFixed(2)}`;
    }
    return points.map((point, index) =>
      `${index ? "L" : "M"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
  }).join(" ");
  const area = segments.filter(points => points.length > 1).map(points => {
    const path = points.map((point, index) =>
      `${index ? "L" : "M"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
    return `${path} L${points.at(-1).x.toFixed(2)},${height} L${points[0].x.toFixed(2)},${height} Z`;
  }).join(" ");
  return { line, area };
}

function historyAxisTicks(data, range) {
  const startMs = Number(data.start_ms);
  const endMs = Number(data.end_ms);
  const timeLabel = (timestamp, seconds = false) => new Intl.DateTimeFormat(formatLocale(), {
    hour: "2-digit",
    minute: "2-digit",
    second: seconds ? "2-digit" : undefined,
    hourCycle: "h23",
  }).format(new Date(timestamp));
  if (range === "realtime") {
    return Array.from({ length: 5 }, (_, index) => {
      const timestampMs = startMs + ((endMs - startMs) * index) / 4;
      return { label: timeLabel(timestampMs, true), timestamp_ms: timestampMs };
    });
  }
  if (range === "day") {
    return Array.from({ length: 5 }, (_, index) => {
      const timestampMs = startMs + ((endMs - startMs) * index) / 4;
      return {
        label: index === 4 ? "24:00" : timeLabel(timestampMs),
        timestamp_ms: timestampMs,
      };
    });
  }
  if (range === "week") {
    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(startMs);
      date.setDate(date.getDate() + index);
      const weekday = new Intl.DateTimeFormat(formatLocale(), { weekday: "short" }).format(date);
      return {
        label: `${weekday} ${date.getMonth() + 1}/${date.getDate()}`,
        timestamp_ms: date.getTime(),
      };
    });
  }
  return Array.from({ length: 5 }, (_, index) => {
    const timestamp = index === 4 ? endMs - 1 : startMs + ((endMs - startMs) * index) / 4;
    const date = new Date(timestamp);
    return { label: `${date.getMonth() + 1}/${date.getDate()}`, timestamp_ms: timestamp };
  });
}

function historyWindowLabel(range) {
  return t({
    realtime: "trend.realtimeLabel",
    day: "trend.dayLabel",
    week: "trend.weekLabel",
    month: "trend.monthLabel",
  }[range] || "trend.defaultWindow");
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

function nearestHistorySample(samples, targetMs) {
  if (!samples.length || !Number.isFinite(Number(targetMs))) return null;
  let low = 0;
  let high = samples.length - 1;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const timestamp = Number(samples[middle].timestamp_ms);
    if (timestamp === targetMs) return samples[middle];
    if (timestamp < targetMs) low = middle + 1;
    else high = middle - 1;
  }
  if (low <= 0) return samples[0];
  if (low >= samples.length) return samples.at(-1);
  const before = samples[low - 1];
  const after = samples[low];
  return targetMs - Number(before.timestamp_ms) <= Number(after.timestamp_ms) - targetMs
    ? before
    : after;
}

function chartTooltipTime(timestampMs) {
  return new Intl.DateTimeFormat(formatLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(new Date(timestampMs));
}

function hideChartTooltip() {
  state.chartHoverSample = null;
  state.chartHoverRatio = null;
  $("#chart-cursor").hidden = true;
  $("#chart-tooltip").hidden = true;
}

function renderChartTooltip(sample) {
  const meta = state.historyMeta;
  if (!sample || !meta) {
    hideChartTooltip();
    return;
  }
  state.chartHoverSample = sample;
  const chart = $("#throughput-chart");
  const cursor = $("#chart-cursor");
  const tooltip = $("#chart-tooltip");
  const rect = chart.getBoundingClientRect();
  const duration = Math.max(1, Number(meta.end_ms) - Number(meta.start_ms));
  const ratio = Math.max(0, Math.min(1,
    (Number(sample.timestamp_ms) - Number(meta.start_ms)) / duration));
  const cursorX = ratio * rect.width;
  cursor.style.left = `${cursorX}px`;
  cursor.hidden = false;
  $("#chart-tooltip-time").textContent = chartTooltipTime(Number(sample.timestamp_ms));
  $("#chart-tooltip-decode").textContent = `${number(sample.decode, 1)} tok/s`;
  $("#chart-tooltip-prefill").textContent = `${number(sample.prefill, 1)} tok/s`;
  tooltip.hidden = false;
  const tooltipLeft = Math.max(8, Math.min(
    rect.width - tooltip.offsetWidth - 8,
    cursorX + 12,
  ));
  tooltip.style.left = `${tooltipLeft}px`;
}

function showChartTooltipAt(clientX) {
  const chart = $("#throughput-chart");
  const meta = state.historyMeta;
  if (!meta || !state.history.length) {
    hideChartTooltip();
    return;
  }
  const rect = chart.getBoundingClientRect();
  if (rect.width <= 0) return;
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  state.chartHoverRatio = ratio;
  const targetMs = Number(meta.start_ms)
    + (Number(meta.end_ms) - Number(meta.start_ms)) * ratio;
  renderChartTooltip(nearestHistorySample(state.history, targetMs));
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

function updateHistoryAxes(data, range) {
  const axis = $(".chart-axis");
  const ticks = historyAxisTicks(data, range);
  const duration = Math.max(1, Number(data.end_ms) - Number(data.start_ms));
  axis.replaceChildren(...ticks.map(tick => {
    const label = textElement("span", "", tick.label);
    const position = ((tick.timestamp_ms - Number(data.start_ms)) / duration) * 100;
    label.style.left = `${Math.max(0, Math.min(100, position))}%`;
    return label;
  }));
}

async function loadHistory(reportError = false) {
  const requestedRange = state.historyRange;
  const requestId = ++state.historyRequestId;
  try {
    const params = new URLSearchParams({ range: requestedRange });
    if (requestedRange !== "realtime" && !state.historyFollowingCurrent && state.historyAnchorMs) {
      params.set("anchor_ms", String(state.historyAnchorMs));
    }
    const data = await api(`/api/history?${params}`);
    if (requestId !== state.historyRequestId || requestedRange !== state.historyRange) return;
    state.history = data.samples || [];
    state.historyMeta = data;
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
    updateHistoryAxes(data, requestedRange);
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
  hideChartTooltip();
  state.historyRange = range;
  state.historyAnchorMs = null;
  state.historyFollowingCurrent = true;
  state.historyNavigationBusy = false;
  state.history = [];
  state.historyMeta = null;
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
  hideChartTooltip();
  $("#history-prev").disabled = true;
  $("#history-next").disabled = true;
  state.historyFollowingCurrent = false;
  state.historyAnchorMs = direction < 0
    ? state.historyMeta.start_ms - 1
    : state.historyMeta.end_ms;
  state.history = [];
  drawChart();
  loadHistory(true);
}

function drawChart() {
  const width = 900;
  const height = 220;
  const decode = state.history.map(item => item.decode);
  const prefill = state.history.map(item => item.prefill);
  const maxValue = Math.max(1, ...decode, ...prefill) * 1.08;
  const endMs = state.historyMeta?.end_ms ?? Date.now();
  const startMs = state.historyMeta?.start_ms ?? endMs - 5 * 60_000;
  const bucketMs = state.historyMeta?.bucket_ms ?? 2_000;
  const compressed = state.historyMeta?.compression === "average_peak_envelope";
  const decodeGeometry = chartGeometry(state.history, "decode", width, height, maxValue, startMs, endMs, bucketMs, compressed);
  const prefillGeometry = chartGeometry(state.history, "prefill", width, height, maxValue, startMs, endMs, bucketMs, compressed);
  $("#decode-line").setAttribute("d", decodeGeometry.line);
  $("#prefill-line").setAttribute("d", prefillGeometry.line);
  $("#decode-area").setAttribute("d", decodeGeometry.area);
  $("#prefill-area").setAttribute("d", prefillGeometry.area);
  if (state.chartHoverRatio !== null) {
    const targetMs = startMs + (endMs - startMs) * state.chartHoverRatio;
    const refreshed = nearestHistorySample(state.history, targetMs);
    if (refreshed) renderChartTooltip(refreshed);
    else hideChartTooltip();
  }
}

function buildChartGrid() {
  const group = $(".chart-grid");
  for (let index = 0; index <= 4; index += 1) {
    const y = 10 + index * 52;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", "0"); line.setAttribute("x2", "900");
    line.setAttribute("y1", String(y)); line.setAttribute("y2", String(y));
    group.append(line);
  }
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
]);
const CONFIG_BOOL_FIELDS = new Set([
  "lm_head_draft", "vision", "preserve_thinking", "prefix_reuse", "cuda_graph",
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
    state.preview = null;
    populateConfig(data.config);
    $("#compose-path").textContent = data.compose_path;
    $("#revision-badge").textContent = `REV ${data.revision}`;
    $("#config-diff").textContent = t("settings.previewHint");
    $("#apply-config").disabled = true;
  } catch (error) {
    toast(error.message, true);
  }
}

async function previewConfig(event) {
  event.preventDefault();
  try {
    const data = await api("/api/config/preview", {
      method: "POST",
      body: JSON.stringify({ config: configFromForm() }),
    });
    state.preview = data;
    state.revision = data.revision;
    $("#revision-badge").textContent = `REV ${data.revision}`;
    $("#config-diff").textContent = data.diff || t("settings.noChanges");
    $("#apply-config").disabled = !data.diff;
    toast(t(data.diff ? "settings.previewReady" : "settings.configUnchanged"));
  } catch (error) {
    state.preview = null;
    $("#apply-config").disabled = true;
    $("#config-diff").textContent = error.message;
    toast(error.message, true);
  }
}

function syncSpecFields() {
  const form = $("#settings-form");
  const off = form.elements.spec.value === "off";
  form.elements.draft_tokens.disabled = off;
  form.elements.lm_head_draft.disabled = off;
  if (off) form.elements.lm_head_draft.checked = false;
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

async function applyConfig() {
  if (!state.preview?.diff) return;
  const confirmed = await confirmAction({
    titleKey: "settings.applyTitle",
    messageKey: "settings.applyMessage",
    phrase: "APPLY CONFIG",
    buttonKey: "settings.applyButton",
  });
  if (!confirmed) return;
  try {
    const data = await api("/api/config/apply", {
      method: "POST",
      body: JSON.stringify({
        config: state.preview.config,
        revision: state.preview.revision,
        confirmation: "APPLY CONFIG",
      }),
    });
    toast(t("settings.applied"));
    await loadConfig();
  } catch (error) {
    toast(error.message, true);
  }
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
    updateHistoryAxes(state.historyMeta, state.historyRange);
  }
  if (state.config) {
    $("#config-diff").textContent = state.preview?.diff
      ? state.preview.diff
      : t(state.preview ? "settings.noChanges" : "settings.previewHint");
  }
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
  if (state.chartHoverSample) renderChartTooltip(state.chartHoverSample);
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
  $("#settings-form").addEventListener("submit", previewConfig);
  $("#reset-config").addEventListener("click", loadConfig);
  $("#apply-config").addEventListener("click", applyConfig);
  $("#start-service").addEventListener("click", startService);
  $("#stop-service").addEventListener("click", stopService);
  $("#restart-service").addEventListener("click", restartService);
  $("#clear-history").addEventListener("click", clearHistory);
  $("#history-delete-start").addEventListener("change", event => {
    const end = $("#history-delete-end");
    if (end.value < event.target.value) end.value = event.target.value;
  });
  $("#throughput-chart").addEventListener("pointermove", event => {
    showChartTooltipAt(event.clientX);
  });
  $("#throughput-chart").addEventListener("pointerdown", event => {
    showChartTooltipAt(event.clientX);
  });
  $("#throughput-chart").addEventListener("pointerleave", event => {
    if (event.pointerType !== "touch") hideChartTooltip();
  });
  document.addEventListener("pointerdown", event => {
    if (!$(".chart-wrap").contains(event.target)) hideChartTooltip();
  });
  $$("[data-history-range]").forEach(button => {
    button.addEventListener("click", () => setHistoryRange(button.dataset.historyRange));
  });
  $("#history-prev").addEventListener("click", () => shiftHistoryPeriod(-1));
  $("#history-next").addEventListener("click", () => shiftHistoryPeriod(1));
  $("#settings-form").elements.spec.addEventListener("change", syncSpecFields);
  $("#confirm-input").addEventListener("input", event => {
    $("#confirm-submit").disabled = event.target.value !== $("#confirm-phrase").textContent;
  });
}

function init() {
  buildChartGrid();
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
    chartGeometry,
    confirmationState,
    historyAxisTicks,
    historyDeleteRange,
    kvCacheUsage,
    lanApiAddress,
    languageFromPreferences,
    localizeApiError,
    nearestHistorySample,
    resolveLocale,
    serviceConfirmationOptions,
    setLanguageMode,
    slotKvUsage,
    slotStage,
    t,
  };
}

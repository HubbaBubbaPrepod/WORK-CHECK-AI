const translations = {
  ru: {
    sys_config: "[ SYS.CONFIG ]",
    api_keys_label: "API Keys (один на строку)",
    use_env_key_btn: "[ USE_ENV_KEY ]",
    fetch_models_btn: "[ FETCH_MODELS ]",
    llm_model_label: "LLM Model",
    model_placeholder: "-- ожидание связи --",
    max_workers_label: "Max Workers / Потоков",
    force_parse_main: "ПРИНУДИТЕЛЬНЫЙ РАЗБОР",
    force_parse_sub: "Обойти кэш и пересобрать (--force)",
    run_btn_text: "ЗАПУСТИТЬ_АНАЛИЗ",
    stop_btn_text: "ОСТАНОВИТЬ",
    dir_html_reports: "[ ПАПКА: html_reports ]",
    cache_data: "[ КЭШ_ДАННЫХ ]",
    toggle_view_btn: "Показать/Скрыть",
    stdout_log_title: "[ STDOUT // ЖУРНАЛ_ВЫПОЛНЕНИЯ ]",
    flush_buffer_btn: "Очистить буфер",
    status_label: "СТАТУС:",
    status_idle: "ГОТОВ_К_РАБОТЕ",
    systime_label: "СИСТ_ВРЕМЯ_",

    init_analysis: "СИСТЕМА: Инициализация основных протоколов анализа...",
    buffer_flushed: "Буфер очищен. Готов к вводу.",
    fatal_no_api_keys: "КРИТИЧЕСКАЯ ОШИБКА: Не введено ни одного API Key.",
    fatal_no_model: "КРИТИЧЕСКАЯ ОШИБКА: Не выбрана модель вычислений.",
    warn_connection_severed:
      "ПРЕДУПРЕЖДЕНИЕ: Соединение преждевременно разорвано.",
    process_terminated: "ПРОЦЕСС ЗАВЕРШЁН. КОД ВЫХОДА:",
    critical_error: "КРИТИЧЕСКАЯ ОШИБКА:",
    websocket_fault: "ОШИБКА WEBSOCKET:",
    alert_no_env_key: "Ключи не заданы в .env. Добавьте OPENROUTER_API_KEYS или OPENROUTER_API_KEY.",
    alert_no_api_input: "Введите хотя бы один API Key или используйте ENV ключ.",
    select_model_first: "Сначала выберите модель LLM.",
    fetching_models: "[ ЗАПРОС МОДЕЛЕЙ... ]",
    error_fetch_models: "[ ОШИБКА: НЕ УДАЛОСЬ ЗАГРУЗИТЬ МОДЕЛИ ]",
    stop_requested: "Запрошена остановка процесса...",
    process_aborted: "Процесс остановлен пользователем.",
    stop_not_running: "Нет запущенного процесса для остановки.",
    select_llm_default: "-- ВЫБЕРИТЕ LLM --",
    tokens_short: "токенов",
    awaiting_uplink: "-- ожидание связи --",
  },
  en: {
    sys_config: "[ SYS.CONFIG ]",
    api_keys_label: "API Keys (one per line)",
    use_env_key_btn: "[ USE_ENV_KEY ]",
    fetch_models_btn: "[ FETCH_MODELS ]",
    llm_model_label: "LLM Model",
    model_placeholder: "-- awaiting uplink --",
    max_workers_label: "Max Workers / Threads",
    force_parse_main: "FORCE RE-PARSE",
    force_parse_sub: "Bypass cache & rebuild (--force)",
    run_btn_text: "INIT_ANALYSIS",
    stop_btn_text: "STOP",
    dir_html_reports: "[ DIR: html_reports ]",
    cache_data: "[ CACHE_DATA ]",
    toggle_view_btn: "Toggle View",
    stdout_log_title: "[ STDOUT // EXECUTION_LOG ]",
    flush_buffer_btn: "Flush Buffer",
    status_label: "STATUS:",
    status_idle: "IDLE_READY",
    systime_label: "SYSTIME_",

    init_analysis: "SYSTEM: Initializing primary analysis protocols...",
    buffer_flushed: "Buffer flushed. Ready for input.",
    fatal_no_api_keys: "FATAL: No API Keys provided.",
    fatal_no_model: "FATAL: No model selected.",
    warn_connection_severed: "WARN: Connection severed prematurely.",
    stop_requested: "Stop requested...",
    process_aborted: "Process aborted by user.",
    stop_not_running: "No active process to stop.",
    process_terminated: "PROCESS TERMINATED. EXIT CODE:",
    critical_error: "CRITICAL ERROR:",
    websocket_fault: "WEBSOCKET FAULT:",
    alert_no_env_key: "Keys not set in .env. Add OPENROUTER_API_KEYS or OPENROUTER_API_KEY.",
    alert_no_api_input: "Input at least one API Key or link ENV data.",
    select_model_first: "Please select an LLM model first.",
    fetching_models: "[ FETCHING MODELS... ]",
    error_fetch_models: "[ ERROR: MODEL FETCH FAILED ]",
    select_llm_default: "-- SELECT LLM --",
    tokens_short: "tkns",
    awaiting_uplink: "-- awaiting uplink --",
  },
};

let currentLang = localStorage.getItem("language") || "ru";

function t(key, params = {}) {
  let str = translations[currentLang]?.[key] || translations["ru"][key] || key;
  for (const [k, v] of Object.entries(params)) {
    str = str.replace(`{{${k}}}`, v);
  }
  return str;
}

function applyLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) el.textContent = t(key);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (key) el.placeholder = t(key);
  });

  const statusSpan = document.getElementById("logStatus");
  if (
    statusSpan &&
    statusSpan.getAttribute("data-i18n") === "status_idle" &&
    !statusSpan.textContent.includes("PROCESSING") &&
    !statusSpan.textContent.includes("HALTED")
  ) {
    statusSpan.textContent = t("status_idle");
  }

  const modelSelect = document.getElementById("model");
  if (
    modelSelect &&
    modelSelect.options.length > 0 &&
    modelSelect.options[0].value === ""
  ) {
    modelSelect.options[0].textContent = t("awaiting_uplink");
  }
}

function setLanguage(lang) {
  if (!translations[lang]) return;
  currentLang = lang;
  localStorage.setItem("language", lang);
  applyLanguage();
  updateModelSelectTexts();
}

function updateModelSelectTexts() {
  const modelSelect = document.getElementById("model");
  if (!modelSelect) return;
  for (let i = 0; i < modelSelect.options.length; i++) {
    const opt = modelSelect.options[i];
    if (opt.value === "") {
      opt.textContent = t("awaiting_uplink");
    } else {
      let text = opt.textContent;
      if (text.includes("tkns") || text.includes("токенов")) {
        text = text.replace(
          /\((\d+)\s*(tkns|токенов)\)/i,
          `($1 ${t("tokens_short")})`,
        );
        opt.textContent = text;
      }
    }
  }
}

let ws = null;
let logContainer = document.getElementById("logContainer");
let logStatus = document.getElementById("logStatus");
let statusIndicator = document.getElementById("statusIndicator");

setInterval(() => {
  const d = new Date();
  document.getElementById("sysTime").textContent =
    d.getHours().toString().padStart(2, "0") +
    ":" +
    d.getMinutes().toString().padStart(2, "0") +
    ":" +
    d.getSeconds().toString().padStart(2, "0");
}, 1000);

function addLogLine(text, type = "stdout") {
  const lineDiv = document.createElement("div");
  lineDiv.className = "log-line font-mono";

  if (text.includes("⚠️ ОПАСНО") || text.includes("DANGER"))
    lineDiv.classList.add("danger");
  else if (text.includes("✅ Безопасно") || text.includes("SAFE"))
    lineDiv.classList.add("safe");
  else if (
    text.includes("Ошибка") ||
    text.includes("ERROR") ||
    type === "stderr"
  )
    lineDiv.classList.add("error");
  else lineDiv.classList.add("stdout");

  const timeStr = new Date().toISOString().substring(11, 19);
  lineDiv.innerHTML = `<span class="opacity-40 mr-3">[${timeStr}]</span>${text}`;

  logContainer.appendChild(lineDiv);
  lineDiv.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function clearLog() {
  logContainer.innerHTML = "";
  addLogLine(t("buffer_flushed"));
}

function stopRun() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "abort" }));
    addLogLine(t("stop_requested"), "stdout");
    logStatus.textContent = "ABORT_REQUESTED";
    statusIndicator.className =
      "inline-block w-2 h-2 rounded-full bg-error-warn animate-pulse mr-3";
  } else {
    addLogLine(t("stop_not_running"), "error");
  }
}

async function loadFiles() {
  const res = await fetch("/api/files");
  const data = await res.json();
  const container = document.getElementById("fileList");
  container.innerHTML = data.files
    .map(
      (f) =>
        `<div class="hover:text-gray-200 transition-colors cursor-default">└─ ${f}</div>`,
    )
    .join("");
}

async function loadCache() {
  const res = await fetch("/api/cache");
  const data = await res.json();
  const viewer = document.getElementById("jsonViewer");
  if (data.exists && data.data) {
    viewer.textContent = JSON.stringify(data.data, null, 2);
  } else {
    viewer.textContent =
      "// parsed_messages.json NOT FOUND.\n// Run analysis to generate databank.";
  }
}

// Загрузка моделей по первому ключу из textarea
async function loadModels() {
  const apiKeysText = document.getElementById("apiKeys").value.trim();
  const apiKeys = apiKeysText.split(/\r?\n/).filter(k => k.trim() !== "");
  if (apiKeys.length === 0) {
    alert(t("alert_no_api_input"));
    return;
  }
  const firstKey = apiKeys[0];
  const modelSelect = document.getElementById("model");
  modelSelect.innerHTML = `<option value="">${t("fetching_models")}</option>`;
  try {
    const res = await fetch("/api/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: firstKey }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const models = data.models || [];
    modelSelect.innerHTML = `<option value="">${t("select_llm_default")}</option>`;
    for (const m of models) {
      const option = document.createElement("option");
      option.value = m.id;
      option.textContent = `${m.name} (${m.context_length} ${t("tokens_short")})`;
      option.className = "bg-black text-gray-300";
      modelSelect.appendChild(option);
    }
    const savedModel = localStorage.getItem("selectedModel");
    if (
      savedModel &&
      modelSelect.querySelector(`option[value="${savedModel}"]`)
    ) {
      modelSelect.value = savedModel;
    }
    updateModelSelectTexts();
  } catch (err) {
    modelSelect.innerHTML = `<option value="">${t("error_fetch_models")}</option>`;
    console.error(err);
  }
}

document.getElementById("toggleJsonBtn").addEventListener("click", () => {
  const viewer = document.getElementById("jsonViewer");
  viewer.classList.toggle("hidden");
});

document.getElementById("clearLogBtn").addEventListener("click", clearLog);
document.getElementById("loadModelsBtn").addEventListener("click", loadModels);
document.getElementById("stopBtn").addEventListener("click", stopRun);

// Кнопка USE_ENV_KEY – загружает ключи из .env
document.getElementById("useEnvKeyBtn").addEventListener("click", async () => {
  const res = await fetch("/api/env_keys");
  const data = await res.json();
  if (data.keys && data.keys.length > 0) {
    const textarea = document.getElementById("apiKeys");
    textarea.value = data.keys.join("\n");
    textarea.style.borderColor = "var(--safe-green)";
    localStorage.setItem("useEnvKey", "true");
    // автоматически загружаем модели по первому ключу
    await loadModels();
  } else {
    alert(t("alert_no_env_key"));
  }
});

document.getElementById("runBtn").addEventListener("click", async () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
    await new Promise((r) => setTimeout(r, 500));
  }
  clearLog();
  addLogLine(t("init_analysis"), "stdout");
  logStatus.textContent = "CONNECTING...";
  statusIndicator.className =
    "inline-block w-2 h-2 rounded-full bg-error-warn animate-pulse mr-3";

  const apiKeysText = document.getElementById("apiKeys").value.trim();
  let apiKeys = apiKeysText.split(/\r?\n/).filter(k => k.trim() !== "");
  if (apiKeys.length === 0) {
    addLogLine(t("fatal_no_api_keys"), "error");
    logStatus.textContent = "ERR_NO_AUTH";
    statusIndicator.className =
      "inline-block w-2 h-2 rounded-full bg-danger-red mr-3";
    return;
  }
  const model = document.getElementById("model").value;
  if (!model) {
    addLogLine(t("fatal_no_model"), "error");
    logStatus.textContent = "ERR_NO_MODEL";
    statusIndicator.className =
      "inline-block w-2 h-2 rounded-full bg-danger-red mr-3";
    return;
  }
  const maxWorkers = parseInt(document.getElementById("maxWorkers").value);
  const force = document.getElementById("forceParse").checked;

  localStorage.setItem("selectedModel", model);

  ws = new WebSocket("ws://localhost:8000/ws/run");
  ws.onopen = () => {
    ws.send(
      JSON.stringify({
        api_keys: apiKeys,
        model: model,
        max_workers: maxWorkers,
        max_retries: 10,
        force: force,
        folder: "./html_reports",
        cache_file: "parsed_messages.json",
        output_csv: "dangerous_openrouter.csv",
      }),
    );
    logStatus.textContent = "PROCESSING...";
    statusIndicator.className =
      "inline-block w-2 h-2 rounded-full bg-safe-green animate-pulse mr-3";
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "stdout" || data.type === "stderr") {
      addLogLine(data.line, data.type);
    } else if (data.type === "exit") {
      addLogLine(`${t("process_terminated")} ${data.code}`);
      logStatus.textContent = `HALTED_CODE_${data.code}`;
      statusIndicator.className =
        "inline-block w-2 h-2 rounded-full bg-gray-500 mr-3";
      ws.close();
    } else if (data.type === "error") {
      addLogLine(`${t("critical_error")} ${data.message}`, "error");
      logStatus.textContent = "SYS_ERROR";
      statusIndicator.className =
        "inline-block w-2 h-2 rounded-full bg-danger-red mr-3";
      ws.close();
    }
  };

  ws.onclose = () => {
    if (!logStatus.textContent.includes("HALTED")) {
      addLogLine(t("warn_connection_severed"));
      logStatus.textContent = "DISCONNECTED";
      statusIndicator.className =
        "inline-block w-2 h-2 rounded-full bg-error-warn mr-3";
    }
  };

  ws.onerror = (err) => {
    addLogLine(`${t("websocket_fault")} ${err}`, "error");
    logStatus.textContent = "WS_FAULT";
    statusIndicator.className =
      "inline-block w-2 h-2 rounded-full bg-danger-red mr-3";
  };
});

document.getElementById("langSwitcher").addEventListener("change", (e) => {
  setLanguage(e.target.value);
});

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("langSwitcher").value = currentLang;
  applyLanguage();
  if (localStorage.getItem("useEnvKey") === "true") {
    // если ранее использовали ENV, подтянем ключи автоматически
    fetch("/api/env_keys")
      .then(res => res.json())
      .then(data => {
        if (data.keys && data.keys.length) {
          document.getElementById("apiKeys").value = data.keys.join("\n");
          document.getElementById("apiKeys").style.borderColor = "var(--safe-green)";
          loadModels();
        }
      });
  }
  loadFiles();
  loadCache();
});
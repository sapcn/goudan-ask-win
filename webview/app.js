// 狗蛋问问 Windows 版 — WebView front-end（GLM 版）
// 注入：window.GOUDAN_CTX（Python panel.py evaluate_js 注入）
// 桥：window.pywebview.api（hide_window / recapture）
//
// 与 macOS 版的差别：
// - 单一网络路径 fetch("/api/llm")（本地中继同源，零 CORS；key 在 Python 端）
// - Gemini parts → GLM OpenAI 格式（content 数组 + image_url + system role）
// - webkit.messageHandlers → pywebview js_api

const $ctxApp    = document.getElementById("ctx-app");
const $ctxMode   = document.getElementById("ctx-mode");
const $ctxBody   = document.getElementById("ctx-body");
const $ctxPrev   = document.getElementById("ctx-preview");
const $ctxTog    = document.getElementById("ctx-toggle");
const $chat      = document.getElementById("chat");
const $form      = document.getElementById("input-form");
const $input     = document.getElementById("input");
const $send      = document.getElementById("btn-send");
const $close     = document.getElementById("btn-close");
const $lookupHead= document.getElementById("lookup-head");
const $lookupTerm= document.getElementById("lookup-term");
const $followBar = document.getElementById("followup-bar");
const $btnFollow = document.getElementById("btn-followup");

// 这些在 goudanStart() 里赋值（等 Python 注入完 ctx 再启动）
let ctx = null;
let isLookupMode = false;
let USER_NAME = "朋友"; // prompts.js 默认称呼，config 拉到后覆盖
// history 只存纯文本对话，每次请求时把当前 ctx 的图/文拼到最新一轮
// 这样切换页面/选词时旧图不会重复发，省 token（原版同款策略）
const history = []; // [{ role: 'user'|'assistant', text: '...' }]

// 启动即拉用户配置（称呼）；失败静默用默认
fetch("/api/config").then((r) => r.json()).then((c) => {
  if (c && c.user_name) {
    USER_NAME = c.user_name;
    window.GoudanPrompts.setUser(USER_NAME);
  }
}).catch(() => {});

// ── 初始化上下文显示 ───────────────────────────────────────────────
function initContext() {
  $ctxMode.textContent = ({
    browser: "WEB", screenshot: "SHOT", file: "FILE", none: "--",
  })[ctx.mode] || String(ctx.mode || "--").toUpperCase();

  const parts = [];
  if (ctx.title) parts.push(`【标题】${ctx.title}`);
  if (ctx.url) parts.push(`【URL】${ctx.url}`);
  if (ctx.text) parts.push(`【正文】${ctx.text.slice(0, 1500)}${ctx.text.length > 1500 ? "…" : ""}`);
  $ctxBody.textContent = parts.join("\n\n");
  if (ctx.image_base64) {
    const img = new Image();
    img.src = `data:image/png;base64,${ctx.image_base64}`;
    $ctxBody.appendChild(img);
  }
}

$ctxTog.addEventListener("click", () => {
  $ctxPrev.classList.toggle("collapsed");
  $ctxTog.textContent = $ctxPrev.classList.contains("collapsed")
    ? "[+] 展开上下文" : "[-] 收起上下文";
});

// ── system instruction（提示词在 prompts.js，UMD 共用）─────────────
function buildSystemInstruction(searchEnabled) {
  return window.GoudanPrompts.buildSystemInstruction(ctx, isLookupMode, searchEnabled);
}

// ── 构造当前轮 user content（GLM OpenAI 多模态格式）────────────────
// 每次请求都用当前 ctx 重拼，旧轮的图不会重复发
function buildCurrentContent(question) {
  const content = [];
  if (ctx.image_base64) {
    // GLM：base64 直接放 image_url.url（官方文档格式）
    content.push({
      type: "image_url",
      image_url: { url: `data:image/png;base64,${ctx.image_base64}` },
    });
    content.push({
      type: "text",
      text: `（上方截图：${USER_NAME} 当前阅读 — ${ctx.app}${ctx.title ? " / " + ctx.title : ""}）\n\n`,
    });
  }
  if (ctx.text) {
    content.push({
      type: "text",
      text: `当前阅读的内容（节选 — ${ctx.app}）：\n"""\n${ctx.text.slice(0, 6000)}\n"""\n\n`,
    });
  }
  if (ctx.selection && ctx.selection.trim()) {
    content.push({ type: "text", text: `${USER_NAME} 划选的文字：「${ctx.selection}」\n\n` });
  }
  content.push({ type: "text", text: question || `请直接解释 ${USER_NAME} 划选的文字。` });
  return content;
}

// ── 渲染气泡 ─────────────────────────────────────────────────────
function appendMsg(role, text = "") {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  $chat.appendChild(div);
  $chat.scrollTop = $chat.scrollHeight;
  return div;
}
function setError(msg) { appendMsg("err", `⚠️ ${msg}`); }
function renderMd(el, text) {
  const html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  el.innerHTML = html;
}

// ── 什么时候该联网搜（规则在 search-policy.js）─────────────────────
function shouldUseWebSearch(question) {
  return window.GoudanSearchPolicy.shouldUseGoogleSearch(question, { lookupMode: isLookupMode });
}

// ── 调 GLM streaming（经本地中继 /api/llm，同源零 CORS）─────────────
let isAsking = false;
async function ask(question) {
  if (isAsking) return;  // 上一轮还在流，跳过（连续划词不会重叠）
  isAsking = true;

  appendMsg("user", question);
  const aiBubble = appendMsg("ai", "");
  aiBubble.classList.add("thinking");

  // GLM messages：system + 历史轮纯文本 + 当前轮多模态
  const messages = [{ role: "system", content: buildSystemInstruction(shouldUseWebSearch(question)) }];
  for (const h of history) {
    messages.push({ role: h.role, content: h.text });
  }
  history.push({ role: "user", text: question });
  const searchEnabled = shouldUseWebSearch(question);
  messages.push({ role: "user", content: buildCurrentContent(question) });

  // system 提示词里的搜索工具说明要与实际挂载一致，先算好再重建
  messages[0].content = buildSystemInstruction(searchEnabled);

  let acc = "";
  try {
    acc = await askViaProxy(messages, searchEnabled, aiBubble);
  } catch (e) {
    aiBubble.classList.remove("thinking");
    aiBubble.classList.remove("streaming");
    setError(e.message || String(e));
    isAsking = false;
    return;
  }
  aiBubble.classList.remove("thinking");
  aiBubble.classList.remove("streaming");
  isAsking = false;
  if (!acc) { setError("AI 没返回内容"); return; }
  history.push({ role: "assistant", text: acc });
}

// ── 本地中继 SSE 流式（GLM choices[].delta.content）────────────────
async function askViaProxy(messages, searchEnabled, aiBubble) {
  let resp;
  try {
    resp = await fetch("/api/llm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, search: !!searchEnabled }),
    });
  } catch (e) {
    throw new Error(`网络错误: ${e.message}`);
  }
  if (!resp.ok) {
    const txt = await resp.text().catch(() => "");
    let msg = txt.slice(0, 200);
    try { msg = JSON.parse(txt).error || msg; } catch (e) {}
    throw new Error(`API ${resp.status}: ${msg}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "", acc = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const data = line.slice(5).trim();
      if (!data || data === "[DONE]") continue;
      try {
        const delta = JSON.parse(data)?.choices?.[0]?.delta || {};
        const text = delta.content || "";  // reasoning_content 思考流不展示
        if (text) {
          acc += text;
          if (aiBubble.classList.contains("thinking")) {
            aiBubble.classList.remove("thinking");
            aiBubble.classList.add("streaming");
          }
          renderMd(aiBubble, acc);
          $chat.scrollTop = $chat.scrollHeight;
        }
      } catch (e) {}
    }
  }
  return acc;
}

// ── 切到对话模式 ─────────────────────────────────────────────────
function enterChatMode() {
  document.body.classList.remove("mode-lookup");
  document.body.classList.add("mode-chat");
  $followBar.hidden = true;
  $form.hidden = false;
  $input.focus();
}

// ── 分隔条：标记上下文切换 ────────────────────────────────────────
function insertContextDivider() {
  const div = document.createElement("div");
  div.className = "ctx-divider";
  let label = `switched → ${ctx.app}`;
  if (ctx.selection && ctx.selection.trim()) {
    const s = ctx.selection.trim();
    label += `  ·  sel "${s.length > 24 ? s.slice(0, 24) + "…" : s}"`;
  }
  div.textContent = label;
  $chat.appendChild(div);
  $chat.scrollTop = $chat.scrollHeight;
}

$btnFollow.addEventListener("click", enterChatMode);

// ── 表单（对话模式）──────────────────────────────────────────────
$form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $input.value.trim();
  if (!q) return;
  $input.value = "";
  $input.style.height = "auto";
  $send.disabled = true;

  // ⭐ 提交前让 Python 重抓一次画面，AI 看到的就是现在屏幕上的内容
  // 切到新页/滚到新位置后，直接在输入框问「这页讲啥」即可
  await requestRecapture();

  await ask(q);
  $send.disabled = false;
  $input.focus();
});

// 回车不发送（原版习惯），只能点「发送」按钮提交。Enter = 换行
$input.addEventListener("input", () => {
  $input.style.height = "auto";
  $input.style.height = Math.min($input.scrollHeight, 120) + "px";
});

// ── 关闭浮窗（pywebview 桥 → Python window.hide）──────────────────
function closePanel() {
  try { window.pywebview?.api?.hide_window?.(); } catch (e) {}
}
$close.addEventListener("click", closePanel);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closePanel();
});

// ── 启动入口（Python 注入 ctx 后调用 / 调试模式自启）─────────────
window.goudanStart = function() {
  ctx = window.GOUDAN_CTX || {
    app: "调试模式", title: "", mode: "none",
    selection: "", text: "", image_base64: "", url: "",
  };
  isLookupMode = !!(ctx.selection && ctx.selection.trim());

  initContext();

  if (isLookupMode) {
    $lookupHead.hidden = false;
    const sel = ctx.selection.trim();
    $lookupTerm.textContent = sel.length > 80 ? sel.slice(0, 80) + "…" : sel;
    $followBar.hidden = false;
    $form.hidden = true;
    ask(`解释「${sel}」`);
  } else {
    enterChatMode();
  }
};

// ── 刷新入口（Python 注入新 GOUDAN_CTX + __GOUDAN_REFRESH_MODE 后调）─
// mode = "normal" → auto-watch / 热键：插分隔条、可能自动问
// mode = "silent" → 发送前重抓：只更新 ctx，resolve 等待中的 Promise
window.goudanRefresh = function() {
  const mode = window.__GOUDAN_REFRESH_MODE || "normal";
  ctx = window.GOUDAN_CTX || ctx;
  initContext();

  if (mode === "silent") {
    $lookupHead.hidden = true;
    $ctxMode.classList.add("flashing");
    $ctxMode.textContent = `JUST CAPTURED`;
    setTimeout(() => {
      $ctxMode.classList.remove("flashing");
      $ctxMode.textContent = ({
        browser: "WEB", screenshot: "SHOT", file: "FILE", none: "--",
      })[ctx.mode] || String(ctx.mode || "--").toUpperCase();
    }, 1800);
    if (window.__goudanRecaptureResolve) {
      const r = window.__goudanRecaptureResolve;
      window.__goudanRecaptureResolve = null;
      r();
    }
    return;
  }

  // normal 模式：插分隔条 + 自动问（如果有划选）
  insertContextDivider();
  const sel = ctx.selection && ctx.selection.trim();
  if (sel) {
    $lookupHead.hidden = false;
    $lookupTerm.textContent = sel.length > 80 ? sel.slice(0, 80) + "…" : sel;
    enterChatMode();
    ask(`解释「${sel}」`);
  } else {
    $lookupHead.hidden = true;
    enterChatMode();
  }
};

// ── 静默重抓：让 Python 现场抓新截图更新 ctx（pywebview 桥）────────
function requestRecapture() {
  return new Promise((resolve) => {
    window.__goudanRecaptureResolve = resolve;
    try {
      window.pywebview.api.recapture();  // fire-and-forget；结果经 goudanRefresh 回来
    } catch (e) {
      // 不在 Python 宿主里跑（独立调试）→ 直接 resolve
      window.__goudanRecaptureResolve = null;
      resolve();
    }
    setTimeout(() => {
      if (window.__goudanRecaptureResolve === resolve) {
        window.__goudanRecaptureResolve = null;
        resolve();
      }
    }, 3000);
  });
}

// ── 通知 Python：页面 JS 已就绪（panel 靠这个信号才注入 ctx）───────
// pywebview 对象注入可能晚于脚本执行，轮询重试
(function notifyReady(attempt) {
  try {
    window.pywebview.api.page_ready();
  } catch (e) {
    if (attempt < 25) setTimeout(() => notifyReady(attempt + 1), 200);
  }
})(0);

// 调试模式：直接开 index.html（无 Python）时延迟自启
if (!window.GOUDAN_CTX) {
  setTimeout(() => { if (!ctx) window.goudanStart(); }, 250);
}

// ── placeholder 轮播（让输入框「活」着）───────────────────────────
const PLACEHOLDERS = [
  "想问点什么…（点「发送」提交，回车换行）",
  "试试划个新词，我会自动解释",
  "切到新页面就问「这页讲啥」",
  "继续追问到清楚为止",
];
let __phIdx = 0;
setInterval(() => {
  if (document.activeElement === $input) return;
  if ($input.value) return;
  __phIdx = (__phIdx + 1) % PLACEHOLDERS.length;
  $input.placeholder = PLACEHOLDERS[__phIdx];
}, 4200);


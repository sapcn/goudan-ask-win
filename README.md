# 狗蛋问问 · goudan-ask-win

划词问 AI 的 Windows 浮窗工具：在任何应用里**拖拽/双击选中文字**，右侧浮窗立刻结合**当前屏幕截图**给出解释；按 `Alt+Q` 随时唤出对着屏幕提问。

移植自 [Jane-xiaoer/xiaoer-ask](https://github.com/Jane-xiaoer/xiaoer-ask)（macOS + Hammerspoon + Gemini），本版改为 **Windows 11 + Python + GLM（智谱）**——国内直连无需代理，支持 Coding Plan 订阅。

## ✨ 功能总览

### 划词秒查
- **拖拽划词** → 浮窗自动弹出，结合屏幕截图解释选中内容（不是干巴巴的字典释义）
- **双击选词** → 双击选中一个单词，同样自动解释
- **三层抓词**（照搬原版思路）：识别「选中即复制」的终端类应用 → 模拟 `Ctrl+C` → 剪贴板序列号检测
- **剪贴板保护**：划词抓取后自动还原原内容，不污染你的剪贴板
- **智能过滤**：选中长度 2~500 字才触发，单击/误触/整页全选自动忽略

### 对话与上下文
- **持续追问**：多轮对话上下文保留，说「它」「这个」能接上前文
- **发送前自动重抓屏幕**：AI 永远看到你此刻的画面（chip 闪 `JUST CAPTURED`）
- **上下文分隔条**：划新词时插入 `switched → 应用名`，标记话题切换
- **上下文预览**：可折叠查看发给 AI 的截图缩略图 / 窗口标题 / URL
- **智能联网搜索**：说「搜一下」「查查」或问时效性问题（价格/最新/今天…）才挂搜索；划词解释默认离线，快
- **回答渲染**：流式输出 + `代码` / **加粗** 轻量 Markdown

### 浮窗体验
- **右侧贴边垂直居中**：不挡阅读区（原版同款布局）
- **窗口置顶**、可拖动、可拉伸
- **Esc / ✕ = 隐藏不退出**：下次唤出秒开，WebView2 常驻零延迟
- **浮窗内点击免疫**：点浮窗内的文字/按钮不会误触发划词监听
- **动效细节**：窗口入场、AI 扫描线、思考墨点、流式光标、placeholder 轮播

### 窗口识别
- 自动识别前台应用（Chrome/Edge/VS Code/微信/Office 等 20+ 常见应用名映射）
- 浏览器显示 `WEB` 模式并清洗窗口标题后缀，其他应用显示 `SHOT`

### 启动与常驻
- **双击启动**：`启动狗蛋问问.bat`，控制台显示热键提示，关窗即退出
- **开机自启**：一键注册/取消，开机后台最小化待命，不弹窗打扰
- **热键可配置**：默认 `Alt+Q`，改 `.env` 即可换任意组合

### 模型与协议（GLM）
- **双协议自适应**：
  - `anthropic` —— 智谱 **Coding Plan** 订阅 key（走 Anthropic 兼容端点，订阅额度内用，推荐）
  - `openai` —— 标准 API key（按量付费，支持 `web_search` 联网工具）
- **多模态**：默认 `glm-5.3-flash`（原生视觉），也支持 `glm-4v-flash`（免费）等
- **本地中继**：Python 端转发，**API key 永不进网页**；页面与 API 同源，零 CORS 配置

### 隐私与安全
- 对话不落盘、不写日志（原版「阅后即焚」原则）
- API key 只存在本机 `.env`（已被 `.gitignore` 排除）
- 静态服务带路径穿越防护，只绑定 127.0.0.1

## 🚀 快速开始

```bash
# 1. 装依赖（Python 3.10+，Win11 自带 WebView2）
pip install -r requirements.txt

# 2. 配置
copy .env.example .env
#    编辑 .env，填入智谱 key（申请：https://bigmodel.cn/apikey/platform）

# 3. 启动
python -m app.main
```

## 🖱️ 日常启动（免终端）

项目根目录三个双击即用的脚本（路径自适应，clone 到哪里都能用）：

| 脚本 | 作用 |
|------|------|
| `启动狗蛋问问.bat` | 双击启动；控制台驻留任务栏，**关掉它 = 退出程序** |
| `开启开机自启.bat` | 一键注册开机自启（后台最小化待命） |
| `关闭开机自启.bat` | 一键取消开机自启 |

> 开机自启也可以在「任务管理器 → 启动应用」里管理（显示为「狗蛋问问」）。

## ⌨️ 操作速查

| 操作 | 效果 |
|------|------|
| `Alt+Q` | 唤出浮窗：有划选就解释划选，没有就进入对话模式 |
| 浮窗开着时拖拽划词 | 自动解释新词（对话历史保留） |
| 浮窗开着时双击选词 | 同上 |
| 输入框打字 + 点「send ↩」 | 提问（发送前自动重抓屏幕） |
| 回车 | 输入框内换行，**不发送** |
| 「搜索一下…」/ 时效问题 | 自动联网搜索 |
| `Esc` / 点 ✕ | 隐藏浮窗（程序继续驻留） |
| 关闭控制台窗口 | 完全退出程序 |

## ⚙️ 配置（.env）

| 变量 | 默认 | 说明 |
|------|------|------|
| `ZHIPU_API_KEY` | （必填） | 智谱 API key / Coding Plan token |
| `GOUDAN_MODEL` | `glm-5v-turbo` | 模型：`glm-5.3-flash`（Coding Plan）/ `glm-4v-flash`（免费）/ `glm-5v-turbo`（按量） |
| `GOUDAN_API_STYLE` | `openai` | `anthropic`（Coding Plan key）\| `openai`（按量 key） |
| `GOUDAN_USER_NAME` | `AI牧民` | AI 对你的称呼（写进提示词） |
| `GOUDAN_HOTKEY_MOD` | `alt` | 热键修饰键：alt / ctrl / shift / windows |
| `GOUDAN_HOTKEY_KEY` | `q` | 热键主键 |

## 🏗️ 架构

| 模块 | 职责 | 对应原版（Mac） |
|------|------|------|
| `app/main.py` | 总入口：热键（keyboard）+ 鼠标监听（pynput）+ 流程串联 | Hammerspoon 事件tap |
| `app/selection.py` | 三层划词抓取 + 剪贴板还原 | AX/⌘C/changeCount 三层 |
| `app/capture.py` | mss 全屏截图 + 前台窗口识别 | capture-context.sh |
| `app/panel.py` | pywebview 浮窗单例（隐藏预创建、evaluate_js 注入） | hs.webview 浮窗 |
| `app/llm_proxy.py` | 本地中继：静态页 + SSE 流式转发 + **Anthropic↔OpenAI 协议转换** | hs.http 代理中继 |
| `webview/` | UI 层（原版复用 + GLM 协议改造） | webview/ |

**线程模型**：pywebview 主循环 + keyboard/pynput 各自回调线程；跨线程更新经 `evaluate_js` marshal。

**与原版的行为差异**：浏览器 URL/正文抓取（AppleScript）未移植，多模态看截图已覆盖主要场景；thinking 关闭换响应速度；浮窗有关闭栏。

## 🧪 调试

```bash
python -m app.capture               # 看窗口识别 + 截图
python -m app.selection             # 划词抓取单测（3 秒内去别的窗口选字）
python -m app.llm_proxy             # 只起中继，浏览器开 http://127.0.0.1:17321 调 UI
node tests/test-search-policy.js    # 搜索策略 28 项测试
python scripts/fix_bats.py          # 重新生成三个 bat（改内容后跑）
```

## 📄 License

[MIT](LICENSE) — 衍生自 [xiaoer-ask](https://github.com/Jane-xiaoer/xiaoer-ask)（Jane @xiaoerzhan），保留其原始版权声明。

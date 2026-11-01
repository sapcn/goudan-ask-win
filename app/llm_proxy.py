# -*- coding: utf-8 -*-
"""本地 HTTP 中继：serve webview/ 静态页 + /api/llm SSE 流式转发智谱。

为什么需要它：WebView2 里 fetch 国外 API 会有 CORS/网络问题；让页面与
API 同源（http://127.0.0.1:port），浏览器侧零 CORS 配置，且 API key
只存在 Python 端，永远不进网页。

POST /api/llm  body: {"messages":[...], "search": bool, "lookup": bool}
  → 流式转发智谱 chat/completions（stream:true），SSE 原样透传
GET  /            → webview/index.html
GET  /api/config  → {"user_name", "model"}（网页提示词用）
"""
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

from .config import Config, ZHIPU_ANTHROPIC_ENDPOINT, ZHIPU_ENDPOINT

WEBVIEW_DIR = Path(__file__).resolve().parent.parent / "webview"

# 转发智谱的超时：连接 10s；读 90s（带图首包慢，搜索工具更慢）
_UPSTREAM_TIMEOUT = (10, 90)

# Anthropic 协议的 max_tokens 必填；划词/对话场景给足
_ANTHROPIC_MAX_TOKENS = 2048


def _to_anthropic_body(cfg: Config, req: dict) -> dict:
    """网页的 OpenAI 格式 → Anthropic Messages 格式（Coding Plan 端点用）。

    转换点：
    - messages[role=system] → 顶层 system 字段
    - image_url(data URI) → image source(base64)
    - max_tokens 必填
    - 搜索工具暂不挂（Anthropic server-tool 格式智谱端未验证，宁缺毋滥）
    """
    system_text = ""
    messages = []
    for msg in req.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_text += (("\n\n" if system_text else "") + str(content))
            continue
        # content 可能是字符串或 OpenAI 多模态数组
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue
        blocks = []
        for part in content or []:
            ptype = part.get("type")
            if ptype == "text":
                blocks.append({"type": "text", "text": part.get("text", "")})
            elif ptype == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                # 接受 data:image/png;base64,XXX 格式，拆出 media_type 与裸数据
                if url.startswith("data:"):
                    header, _, data = url.partition(",")
                    media = header[5:].split(";")[0] or "image/png"
                    blocks.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media, "data": data},
                    })
        messages.append({"role": role, "content": blocks or [{"type": "text", "text": ""}]})

    body = {
        "model": cfg.model,
        "max_tokens": _ANTHROPIC_MAX_TOKENS,
        "stream": True,
        "messages": messages,
    }
    if system_text:
        body["system"] = system_text
    return body


def make_handler(cfg: Config) -> type:
    """闭包把 cfg 织进 Handler（BaseHTTPRequestHandler 不支持传参）。"""

    class Handler(BaseHTTPRequestHandler):
        # 保持 HTTP/1.0：无 Content-Length 的流式响应天然「读到关闭」，
            # 浏览器 fetch reader 照样逐块收，不必手写 chunked 编码
        def log_message(self, *args):  # 静默访问日志，避免刷屏
            pass

        # ── GET：静态文件 + 配置接口 ──────────────────────────────
        def do_GET(self):
            if self.path == "/api/config":
                body = json.dumps(
                    {"user_name": cfg.user_name, "model": cfg.model},
                    ensure_ascii=False,
                ).encode("utf-8")
                self._send_bytes(body, "application/json; charset=utf-8")
                return

            # 其余一律当静态文件；/ → index.html
            rel = "index.html" if self.path in ("/", "") else self.path.lstrip("/")
            target = (WEBVIEW_DIR / rel).resolve()
            # 路径穿越防护：必须还在 webview/ 里
            if not str(target).startswith(str(WEBVIEW_DIR.resolve())):
                self.send_error(403)
                return
            if not target.is_file():
                self.send_error(404)
                return
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send_bytes(target.read_bytes(), mime)

        def _send_bytes(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        # ── POST /api/llm：SSE 流式转发 ──────────────────────────
        def do_POST(self):
            if self.path != "/api/llm":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError) as e:
                self._send_json_error(400, f"请求体不合法：{e}")
                return

            messages = req.get("messages")
            if not isinstance(messages, list) or not messages:
                self._send_json_error(400, "缺少 messages 数组")
                return

            if cfg.api_style == "anthropic":
                self._relay_anthropic(req)
            else:
                self._relay_openai(req)

        # ── SSE 写出 helpers ─────────────────────────────────────
        def _sse_start(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def _sse_line(self, line: str) -> None:
            data = (line + "\n").encode("utf-8")
            self.wfile.write(data)
            self.wfile.flush()

        # ── 路径 A：标准 OpenAI 协议（按量付费 key）────────────────
        def _relay_openai(self, req: dict) -> None:
            # 拼上游请求体（key 在 Python 端拼，不经过网页）
            upstream = {
                "model": cfg.model,
                "messages": req["messages"],
                "stream": True,
                # 划词秒查要快：关深度思考；追问对话也不需要长推理
                "thinking": {"type": "disabled"},
            }
            if req.get("search"):
                # 智谱联网搜索工具（原版 google_search 的对应物）
                upstream["tools"] = [{
                    "type": "web_search",
                    "web_search": {"enable": True, "search_engine": "search_pro"},
                }]

            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            try:
                upstream_resp = requests.post(
                    ZHIPU_ENDPOINT,
                    json=upstream,
                    headers=headers,
                    stream=True,
                    timeout=_UPSTREAM_TIMEOUT,
                )
            except requests.RequestException as e:
                self._send_json_error(502, f"连不上智谱：{e}")
                return

            if upstream_resp.status_code != 200:
                detail = upstream_resp.text[:300]
                self._send_json_error(502, f"智谱返回 {upstream_resp.status_code}：{detail}")
                upstream_resp.close()
                return

            # 200 → 原样透传 SSE 流
            self._sse_start()
            try:
                for line in upstream_resp.iter_lines(decode_unicode=True):
                    if line is None:
                        continue
                    # SSE 事件行原样透传；空行也要传（事件分隔符）
                    self._sse_line("" if line == "" else line)
            except (BrokenPipeError, ConnectionResetError):
                pass  # 用户关掉了浮窗，正常
            finally:
                upstream_resp.close()

        # ── 路径 B：Anthropic 协议（Coding Plan key 专属端点）──────
        def _relay_anthropic(self, req: dict) -> None:
            body = _to_anthropic_body(cfg, req)
            headers = {
                # Coding Plan token 走 Claude Code 同款 Bearer 头（实测有效）
                "Authorization": f"Bearer {cfg.api_key}",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            try:
                upstream_resp = requests.post(
                    ZHIPU_ANTHROPIC_ENDPOINT,
                    json=body,
                    headers=headers,
                    stream=True,
                    timeout=_UPSTREAM_TIMEOUT,
                )
            except requests.RequestException as e:
                self._send_json_error(502, f"连不上智谱：{e}")
                return

            if upstream_resp.status_code != 200:
                detail = upstream_resp.text[:300]
                self._send_json_error(502, f"智谱返回 {upstream_resp.status_code}：{detail}")
                upstream_resp.close()
                return

            # Anthropic SSE → OpenAI SSE 逐行翻译（网页端零改动）
            self._sse_start()
            try:
                for line in upstream_resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue  # event: 行和空行由我们自己控制输出
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        evt = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    # 正文增量在 content_block_delta.text_delta.text；
                    # thinking_delta 不下发（浮窗不展示思考过程）
                    delta = evt.get("delta") or {}
                    if evt.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        text = delta.get("text") or ""
                        if text:
                            out = json.dumps(
                                {"choices": [{"delta": {"content": text}}]},
                                ensure_ascii=False,
                            )
                            self._sse_line("data: " + out)
                self._sse_line("data: [DONE]")
            except (BrokenPipeError, ConnectionResetError):
                pass  # 用户关掉了浮窗，正常
            finally:
                upstream_resp.close()

        def _send_json_error(self, status: int, msg: str) -> None:
            body = json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def start_server(cfg: Config) -> tuple[ThreadingHTTPServer, str]:
    """启动本地中继（daemon 线程）。返回 (server, base_url)。"""
    httpd = ThreadingHTTPServer(("127.0.0.1", cfg.server_port), make_handler(cfg))
    # 中继只服务本机浮窗，随主线程退出
    threading.Thread(target=httpd.serve_forever, daemon=True, name="llm-proxy").start()
    base = f"http://127.0.0.1:{cfg.server_port}"
    return httpd, base


if __name__ == "__main__":
    # 独立调试：python -m app.llm_proxy
    # 用浏览器开 http://127.0.0.1:17321/ 可直接调试 UI（无热键/浮窗）
    import sys

    from .config import load_config

    try:
        cfg = load_config()
    except RuntimeError as e:
        print(f"[配置错误] {e}")
        sys.exit(1)
    _, base = start_server(cfg)
    print(f"中继已启动：{base}  （Ctrl+C 退出）")
    threading.Event().wait()

# -*- coding: utf-8 -*-
"""浮窗管理：pywebview 单例窗口（对标 macOS 版 hs.canvas/webview 浮窗）。

- 启动即创建隐藏窗口（WebView2 进程提前拉起，首次唤出零延迟）
- 「关闭」= 隐藏不销毁（复用窗口，避免反复建 WebView2 的开销）
- 右侧贴边垂直居中（不挡阅读区，原版同款布局）
- 跨线程更新：热键/鼠标回调线程 → evaluate_js 注入 ctx（pywebview
  内部 marshal 到 GUI 线程，Windows 平台安全）
"""
import ctypes
import json
import threading

import webview

from .config import Config

# 距屏幕右边缘的留白（像素）
_EDGE_MARGIN = 12


def _screen_size() -> tuple[int, int]:
    """主显示器全屏尺寸（物理像素，与 DPI-aware 的 pywebview 坐标一致）。"""
    user32 = ctypes.windll.user32
    return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


class Panel:
    """浮窗单例。GUI 逻辑经 evaluate_js 驱动页面里的 goudanStart/goudanRefresh。"""

    def __init__(self, cfg: Config, base_url: str, on_recapture=None):
        self._cfg = cfg
        self._base = base_url
        self._on_recapture = on_recapture  # 页面提交前请求重抓画面
        self._win: webview.Window | None = None
        self._ready = threading.Event()  # 页面 JS 就绪（page_ready 回调置位）
        self._lock = threading.Lock()
        self._visible = False

    # ── 生命周期 ────────────────────────────────────────────────
    def create_hidden(self) -> None:
        """在 webview.start() 之前调用：创建隐藏窗口。"""
        w, h = self._cfg.panel_width, self._cfg.panel_height
        sw, sh = _screen_size()
        x = max(sw - w - _EDGE_MARGIN, 0)
        y = max((sh - h) // 2, 0)

        self._win = webview.create_window(
            title="狗蛋问问",
            url=self._base,
            width=w,
            height=h,
            x=x,
            y=y,
            resizable=True,       # 可拉伸
            on_top=True,          # 悬浮置顶（原版 NSWindow floating）
            hidden=True,          # 启动即隐藏，首次热键才显示
            easy_drag=False,      # 有关闭栏，不需要无边框拖动
            js_api=self._js_api(),
        )
        # 点「X」= 隐藏（closing 返回 False 阻止销毁）
        self._win.events.closing += self._on_closing

    def _on_closing(self) -> bool:
        self.hide()
        return False  # 阻止窗口销毁，复用

    # ── 页面 → Python 的桥（pywebview js_api）──────────────────
    def _js_api(self):
        panel = self

        class Api:
            def page_ready(self) -> None:
                """页面 JS 全部就绪（app.js 末尾调用）。"""
                panel._ready.set()

            def hide_window(self) -> None:
                """JS 端关闭按钮/Esc 调用。"""
                panel.hide()

            def recapture(self) -> None:
                """JS 端提交前重抓画面（fire-and-forget，结果经 silent 刷新回注）。"""
                cb = panel._on_recapture
                if cb is not None:
                    threading.Thread(target=cb, daemon=True).start()

        return Api()

    # ── 显示 / 刷新 ─────────────────────────────────────────────
    def show_with(self, ctx: dict, mode: str) -> None:
        """带新上下文唤出浮窗。

        mode = "normal" → 划词/热键触发：插分隔条、可能自动问
        mode = "silent" → 发送前重抓：只更新 ctx
        """
        with self._lock:
            if self._win is None:
                return
            self._win.show()
            self._visible = True
            # 首次显示可能页面还没加载完：等 app.js 报到（3s 超时保底）
            self._ready.wait(timeout=3.0)
            self._push(ctx, mode)

    def refresh_with(self, ctx: dict, mode: str) -> None:
        """浮窗已可见时的上下文更新（不重新 show）。"""
        with self._lock:
            if self._win is None or not self._visible:
                return
            self._push(ctx, mode)

    def _push(self, ctx: dict, mode: str) -> None:
        payload = json.dumps(ctx, ensure_ascii=False)
        entry = "window.goudanRefresh" if self._ready.is_set() else "window.goudanStart"
        # 注入 ctx → 快路径（原版 refreshContext：只送划选词，几十字节）
        js = (
            f"window.GOUDAN_CTX = {payload};"
            f"window.__GOUDAN_REFRESH_MODE = {json.dumps(mode)};"
            f"if (typeof {entry} === 'function') {entry}();"
        )
        try:
            self._win.evaluate_js(js)
        except Exception:
            pass  # 窗口刚销毁等极端情况；下次重建

    # ── 状态查询 ────────────────────────────────────────────────
    def is_visible(self) -> bool:
        return self._visible

    def hide(self) -> None:
        self._visible = False
        if self._win is not None:
            try:
                self._win.hide()
            except Exception:
                pass

    def inside(self, x: int, y: int) -> bool:
        """坐标是否落在浮窗内（auto-watch 用来排除浮窗自身区域的点击）。"""
        if self._win is None or not self._visible:
            return False
        try:
            wx, wy = self._win.x, self._win.y
            return (wx <= x <= wx + self._win.width
                    and wy <= y <= wy + self._win.height)
        except Exception:
            return False

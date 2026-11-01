# -*- coding: utf-8 -*-
"""goudan-ask Windows 版总入口。

用法：
  python -m app.main

链路：Alt+A 热键 / 鼠标拖拽划词 → selection 抓词 → capture 截图
      → panel 浮窗 evaluate_js 注入 → 页面 fetch /api/llm → 智谱流式回答。

对标原版 Hammerspoon 的 auto-watch：浮窗可见时，拖拽/双击划词自动问；
浮窗未开时只有热键能唤出（避免平时打扰）。
"""
import threading
import time

import keyboard
import pynput
import webview

from . import selection
from .capture import capture_context
from .config import load_config
from .llm_proxy import start_server
from .panel import Panel

# 拖拽判定：位移 ≥4px（平方和 ≥16，免开方）
_DRAG_SQ = 16
# 双击窗口期（秒）
_DOUBLE_CLICK = 0.5


class GoudanApp:
    """全部可变状态收在实例里（避免全局变量；状态只由鼠标回调线程写）。"""

    def __init__(self) -> None:
        self._cfg = load_config()
        _, base = start_server(self._cfg)
        self._panel = Panel(self._cfg, base, on_recapture=self._recapture_flow)
        self._press_pos: tuple[float, float] | None = None
        self._press_seq = 0
        self._last_release = 0.0

    def _recapture_flow(self) -> None:
        """浮窗输入框提交前的静默重抓：只更新 ctx，不打断对话。"""
        ctx = capture_context("")
        self._panel.refresh_with(ctx, "silent")

    # ── 流程 ────────────────────────────────────────────────────
    def _hotkey_flow(self) -> None:
        """Alt+A：无论浮窗开没开都唤出；抓当前选择（可能是空 → 纯截图问答）。"""
        backup = selection.backup_clipboard_text()
        try:
            sel = selection.capture_selection(selection.get_seq(), settle_delay=0.05)
        finally:
            selection.restore_clipboard_text(backup)
        ctx = capture_context(sel)
        self._panel.show_with(ctx, "normal")

    def _drag_flow(self, seq_baseline: int) -> None:
        """浮窗可见时的拖拽/双击划词 → 自动问（auto-watch）。"""
        backup = selection.backup_clipboard_text()
        try:
            # capture_selection 内部先等 0.18s（app 高亮稳定）再抓
            sel = selection.capture_selection(seq_baseline)
        finally:
            selection.restore_clipboard_text(backup)
        if not sel:
            return  # 没抓到合法划词 → 静默不打扰
        ctx = capture_context(sel)
        self._panel.refresh_with(ctx, "normal")

    # ── 事件回调 ─────────────────────────────────────────────────
    def _on_hotkey(self) -> None:
        # 热键回调里不能做耗时事（截图/Ctrl+C），丢后台线程
        threading.Thread(target=self._hotkey_flow, daemon=True).start()

    def _on_click(self, x: float, y: float, button, pressed: bool) -> None:
        if button != pynput.mouse.Button.left:
            return
        if pressed:
            # 按下：记基线（剪贴板序列号 + 坐标）
            self._press_pos = (x, y)
            self._press_seq = selection.get_seq()
            return

        # 松开
        press_pos, self._press_pos = self._press_pos, None
        if press_pos is None:
            return
        # 浮窗自身区域内的点击不监听（原版 auto-watch 排除浮窗）
        if self._panel.inside(x, y):
            return
        # 浮窗没开 → 不自动问（只有热键能唤出）
        if not self._panel.is_visible():
            return

        dx, dy = x - press_pos[0], y - press_pos[1]
        dragged = (dx * dx + dy * dy) >= _DRAG_SQ
        if not dragged:
            # 单击不算；双击（≤0.5s 内第二次松开）= 双击选词
            now = time.monotonic()
            is_double = now - self._last_release < _DOUBLE_CLICK
            self._last_release = now
            if not is_double:
                return
        seq_baseline, self._press_seq = self._press_seq, 0
        threading.Thread(
            target=self._drag_flow, args=(seq_baseline,), daemon=True
        ).start()

    # ── 启动 ────────────────────────────────────────────────────
    def run(self) -> None:
        cfg = self._cfg
        self._panel.create_hidden()

        hotkey = f"{cfg.hotkey_mod}+{cfg.hotkey_key}"
        keyboard.add_hotkey(hotkey, self._on_hotkey)
        mouse = pynput.mouse.Listener(on_click=self._on_click)
        mouse.start()

        print(f"狗蛋问问已启动（Windows 版 · GLM）")
        print(f"  唤出/划词问答热键：{hotkey.upper()} 替换键位改 .env")
        print(f"  浮窗可见时：拖拽或双击划词 → 自动解释")
        print(f"  关闭本控制台窗口即退出")

        # GUI 主循环（阻塞）。debug=False 不开 DevTools
        webview.start()


def main() -> None:
    try:
        app = GoudanApp()
    except RuntimeError as e:
        print(f"[启动失败] {e}")
        raise SystemExit(1)
    app.run()


if __name__ == "__main__":
    main()

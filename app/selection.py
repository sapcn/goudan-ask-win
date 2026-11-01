# -*- coding: utf-8 -*-
"""划词抓取：模拟 Ctrl+C + 剪贴板序列号检测（对标 macOS 版三层抓取）。

原版三层：AX 焦点元素 → 剪贴板已被 app 改（选中即复制的终端）→ 模拟 ⌘C。
Windows 对应：
  1. AX 层无低成本对应（UI Automation 太重，跳过）
  2. GetClipboardSequenceNumber() 对应 Mac changeCount——鼠标按下时记基线，
     松开时若序列号已变，说明该 app「选中即复制」（终端类），直接读
  3. 否则模拟 Ctrl+C，轮询等序列号变化，变即选中文字进剪贴板

抓完还原剪贴板原内容（只还原文本；原本是图片等格式则不破坏性还原）。
"""
import ctypes
import time

import keyboard
import win32clipboard

# 选中文字长度合法区间（原版同款：太短是误触，太长是整页全选）
MIN_LEN, MAX_LEN = 2, 500

_user32 = ctypes.windll.user32


def get_seq() -> int:
    """剪贴板序列号（每次内容变化 +1，对应 Mac 的 changeCount）。"""
    return _user32.GetClipboardSequenceNumber()


def read_clipboard_text() -> str:
    """读剪贴板纯文本；为空/非文本返回 ''。"""
    try:
        win32clipboard.OpenClipboard()
        try:
            if not win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return ""
            return (win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or "").strip()
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return ""


def _write_clipboard_text(text: str) -> None:
    """把文本写回剪贴板（还原用）。失败静默——还原是尽力而为。"""
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass


def capture_selection(seq_baseline: int, settle_delay: float = 0.18) -> str:
    """鼠标松开后调用：抓划选文字。

    seq_baseline: 鼠标按下时刻的剪贴板序列号（识别「选中即复制」的 app）
    settle_delay: 松开后的等待（原版 0.18s：等 app 高亮稳定、等双击第二击）
    返回合法选中文字；抓不到/长度不合法返回 ''。
    """
    time.sleep(settle_delay)

    # ── 第 2 层：序列号已变 = app 自己写了剪贴板（选中即复制）→ 直接读
    if get_seq() != seq_baseline:
        text = read_clipboard_text()
        if _valid(text):
            return text

    # ── 第 3 层：模拟 Ctrl+C，等序列号变化
    before = get_seq()
    keyboard.send("ctrl+c")

    # 轮询等剪贴板更新（多数 app 50-150ms 内完成；拿不到就放弃）
    for _ in range(12):  # 12 × 30ms ≈ 360ms 上限
        time.sleep(0.03)
        if get_seq() != before:
            break

    if get_seq() == before:
        return ""  # Ctrl+C 没产生任何剪贴板变化 → 没有选中

    text = read_clipboard_text()
    if not _valid(text):
        # 内容变了但不合法（比如 Ctrl+C 把整页复制了）→ 不用
        return ""
    return text


def backup_clipboard_text() -> str:
    """备份当前剪贴板文本（供抓取后还原）。非文本剪贴板返回 ''（还原时跳过）。"""
    return read_clipboard_text()


def restore_clipboard_text(text: str) -> None:
    """还原剪贴板（模拟 Ctrl+C 会覆盖用户原内容，问完还回去）。"""
    if text:
        _write_clipboard_text(text)


def _valid(text: str) -> bool:
    """长度校验：太短是误触，太长是整页全选（原版 2..500 同款）。"""
    if not text:
        return False
    # 去掉换行空白后计数，且不接受含 NUL 的脏数据
    compact = text.replace("\r", "").replace("\n", "").replace("\x00", "")
    return MIN_LEN <= len(compact) <= MAX_LEN


if __name__ == "__main__":
    # 独立调试：python -m app.selection
    # 用法：随便在屏幕上选中一段文字，然后 3 秒内切回终端看输出
    print("3 秒内去别的窗口选一段文字…")
    time.sleep(3)
    base = get_seq()
    backup = backup_clipboard_text()
    sel = capture_selection(base)
    restore_clipboard_text(backup)
    print(f"抓到：{sel!r}" if sel else "没抓到（或长度不合法）")

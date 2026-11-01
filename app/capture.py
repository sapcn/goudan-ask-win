# -*- coding: utf-8 -*-
"""采集层：截屏 + 前台窗口识别 → ctx dict（对标 macOS 版 capture-context.sh）。

原版流程：osascript 取前台 app → 无条件 screencapture → 浏览器抓 URL/正文。
Windows 流程：pywin32 取前台窗口 → mss 全屏截图 → 从进程名识别浏览器。
正文抓取（URL→curl）在国内网站收益低，MVP 靠「截图 + 划词」覆盖，浏览器
分支保留 mode 标记让 UI 显示 WEB。
"""
import base64
import time

import mss
import win32gui
import win32process
from psutil import Process  # type: ignore[import-not-found]

# 进程名 → 应用显示名（覆盖常见场景；未命中时直接用进程名去 .exe）
_APP_NAMES = {
    "chrome": "Google Chrome",
    "msedge": "Microsoft Edge",
    "firefox": "Firefox",
    "opera": "Opera",
    "360se": "360浏览器",
    "qqbrowser": "QQ浏览器",
    "code": "VS Code",
    "idea64": "IntelliJ IDEA",
    "pycharm64": "PyCharm",
    "weixin": "微信",
    "wechat": "微信",
    "wxwork": "企业微信",
    "dingtalk": "钉钉",
    "feishu": "飞书",
    "explorer": "文件资源管理器",
    "eclipse": "Eclipse",
    "WINWORD": "Word",
    "EXCEL": "Excel",
    "POWERPNT": "PowerPoint",
    "ONENOTE": "OneNote",
    "acrobat": "Adobe Acrobat",
}

# 这些进程名视为浏览器（mode=browser）
_BROWSER_PROCS = {"chrome", "msedge", "firefox", "opera", "360se", "qqbrowser"}

# 浏览器窗口标题的固定后缀，清掉后剩页面标题
_BROWSER_SUFFIXES = (
    " - Google Chrome", " - Microsoft​ Edge", " - Microsoft Edge",
    " — Mozilla Firefox", " - Opera", " - 360安全浏览器",
)


def _get_foreground() -> tuple[str, str, str]:
    """取前台窗口 → (应用显示名, 窗口标题, 进程名小写)。

    拿不到就返回占位值，绝不抛异常——截图是兜底主力，窗口信息只是锦上添花。
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ("未知应用", "", "")
        title = win32gui.GetWindowText(hwnd) or ""
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc_name = ""
        try:
            proc_name = Process(pid).name()  # e.g. "chrome.exe"
            proc_name = proc_name.rsplit(".", 1)[0].lower()
        except Exception:
            pass  # 进程可能已退出，忽略
        app = _APP_NAMES.get(proc_name, proc_name.title() if proc_name else "未知应用")
        return (app, title.strip(), proc_name)
    except Exception:
        return ("未知应用", "", "")


def _clean_browser_title(title: str, proc_name: str) -> str:
    """去掉浏览器固定后缀，得到纯页面标题。"""
    if proc_name not in _BROWSER_PROCS:
        return title
    for suffix in _BROWSER_SUFFIXES:
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title


def capture_screenshot() -> str:
    """mss 全屏截图 → PNG base64（原版：无条件先截图，不是兜底）。"""
    try:
        with mss.MSS() as sct:
            # monitor[0] 是虚拟全屏（含多显示器合并）
            raw = sct.grab(sct.monitors[0])
            from mss.tools import to_png  # 局部导入，避免顶层依赖顺序问题
            return base64.b64encode(to_png(raw.rgb, raw.size)).decode("ascii")
    except Exception as e:
        raise RuntimeError(f"截屏失败：{e}") from e


def capture_context(selection: str = "") -> dict:
    """主入口：抓取当前上下文 → ctx dict（字段与 macOS 版对齐）。

    selection 由 selection.py 先抓好传入；这里只负责窗口 + 截图。
    """
    app, title, proc_name = _get_foreground()
    title = _clean_browser_title(title, proc_name)
    mode = "browser" if proc_name in _BROWSER_PROCS else "screenshot"

    image_base64 = ""
    try:
        image_base64 = capture_screenshot()
    except RuntimeError:
        pass  # 截图失败仍可用划词文字问答，不让整条链路挂掉

    return {
        "app": app,
        "title": title,
        "mode": mode,          # browser / screenshot
        "selection": selection,
        "text": "",            # 正文抓取 MVP 不做，靠截图覆盖
        "image_base64": image_base64,
        "url": "",             # 同上
        "ts": time.time(),
    }


if __name__ == "__main__":
    # 独立调试：python -m app.capture
    import json
    ctx = capture_context("测试划词")
    ctx.pop("image_base64")  # 调试输出不打印巨长 base64
    print(json.dumps(ctx, ensure_ascii=False, indent=2))

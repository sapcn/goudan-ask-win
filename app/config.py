# -*- coding: utf-8 -*-
"""配置加载：解析项目根目录 .env，全部只读，不可变配置对象。"""
import os
from dataclasses import dataclass
from pathlib import Path

# 项目根目录（app/ 的上一级）
ROOT = Path(__file__).resolve().parent.parent

# 智谱 API 端点（国内直连，无需代理）
ZHIPU_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
# Coding Plan 专属端点（Anthropic 协议；套餐 key 只在此端点生效）
ZHIPU_ANTHROPIC_ENDPOINT = "https://open.bigmodel.cn/api/anthropic/v1/messages"


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    user_name: str
    api_style: str    # "openai"（按量付费 key）| "anthropic"（Coding Plan key）
    hotkey_mod: str   # alt / ctrl / shift / windows
    hotkey_key: str   # q / a / b / ...
    panel_width: int
    panel_height: int
    server_port: int  # 本地静态+SSE中继端口


def _parse_env() -> dict:
    """极简 .env 解析：KEY=VALUE，忽略注释和空行。不引第三方依赖。"""
    env_path = ROOT / ".env"
    values = {}
    if not env_path.exists():
        return values
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    except OSError as e:
        raise RuntimeError(f"读取 .env 失败：{e}") from e
    return values


def load_config() -> Config:
    """加载配置。.env 优先，缺省值兜底。缺 API key 时给出明确指引。"""
    env = _parse_env()
    # 环境变量再覆盖一层（方便临时改参数不改文件）
    merged = {**env, **{k: os.environ[k] for k in
                        ("ZHIPU_API_KEY", "XIAOER_MODEL", "XIAOER_USER_NAME",
                         "XIAOER_API_STYLE", "XIAOER_HOTKEY_MOD", "XIAOER_HOTKEY_KEY") if k in os.environ}}

    api_key = merged.get("ZHIPU_API_KEY", "")
    if not api_key or api_key == "your-zhipu-api-key-here":
        raise RuntimeError(
            "未配置 ZHIPU_API_KEY。请复制 .env.example 为 .env，"
            "填入智谱 API key（申请：https://bigmodel.cn/console/apikey）"
        )

    api_style = merged.get("XIAOER_API_STYLE", "openai").lower()
    if api_style not in ("openai", "anthropic"):
        api_style = "openai"

    return Config(
        api_key=api_key,
        model=merged.get("XIAOER_MODEL", "glm-5v-turbo"),
        user_name=merged.get("XIAOER_USER_NAME", "AI牧民"),
        api_style=api_style,
        hotkey_mod=merged.get("XIAOER_HOTKEY_MOD", "alt").lower(),
        hotkey_key=merged.get("XIAOER_HOTKEY_KEY", "q").lower(),
        panel_width=480,
        panel_height=620,
        server_port=17321,  # xiaoer 谐音端口，冲突时可在 llm_proxy 里改
    )

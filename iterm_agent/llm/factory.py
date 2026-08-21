"""LLM Provider 工厂：根据配置创建对应实例。"""

from __future__ import annotations

import logging
import os
from typing import Any

from iterm_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# 模型级 temperature 强制覆盖
# 某些模型只接受固定 temperature 值，传入其他值会报 400
FORCED_TEMPERATURE: dict[str, float] = {
    # Moonshot Kimi K2 系列
    "kimi-k2": 1.0,
    "kimi-k2-instruct": 1.0,
    "kimi-k2-thinking": 1.0,
    # Moonshot Kimi K1.5（部分版本）
    "moonshot-v1-128k": 1.0,
    # DeepSeek R1 推理模型
    "deepseek-reasoner": 1.0,
    "deepseek-r1": 1.0,
    # OpenAI o1 / o3 推理模型
    "o1": 1.0,
    "o3": 1.0,
    "o3-mini": 1.0,
}


def _resolve_env(value: str | None) -> str | None:
    """解析 ${ENV_VAR} 格式的环境变量引用。"""
    if value is None:
        return None
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        resolved = os.environ.get(env_name)
        if resolved is None:
            logger.warning(f"环境变量 {env_name} 未设置")
        return resolved
    return value


def get_forced_temperature(model: str) -> float | None:
    """根据模型名返回强制 temperature，无则返回 None。"""
    model_lower = model.lower()
    for prefix, temp in FORCED_TEMPERATURE.items():
        if model_lower.startswith(prefix):
            return temp
    return None


def create_provider(config: dict[str, Any]) -> LLMProvider:
    """根据配置字典创建 LLM Provider 实例。

    当前支持：
    - openai: OpenAI 兼容接口（OpenAI / Moonshot / DeepSeek / vLLM / 任意兼容接口）
    """
    provider_name = config.get("provider", "openai").lower()
    model = config.get("model", "gpt-4o")
    api_key = _resolve_env(config.get("api_key"))
    base_url = config.get("base_url")

    # 检查是否需要强制 temperature
    forced_temp = get_forced_temperature(model)
    if forced_temp is not None:
        logger.info(f"模型 {model} 要求 temperature={forced_temp}，已自动覆盖")

    if provider_name == "openai":
        from iterm_agent.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            forced_temperature=forced_temp,
        )

    else:
        raise ValueError(
            f"未知的 LLM provider: {provider_name}，当前支持: openai（OpenAI 兼容接口）"
        )

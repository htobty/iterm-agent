"""配置加载模块：从 YAML 文件读取 Agent 配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass
class AgentConfig:
    max_react_steps: int = 3
    max_plan_steps: int = 7
    context_window: int = 8000
    auto_confirm: bool = False


@dataclass
class GuardrailConfig:
    enabled: bool = True
    timeout: int = 30


@dataclass
class MemoryConfig:
    long_term_path: str = "~/.iterm_agent/memory.json"
    max_facts: int = 50


@dataclass
class AppConfig:
    """应用完整配置。"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    guardrail: GuardrailConfig = field(default_factory=GuardrailConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """从字典构建配置。"""
        llm_data = data.get("llm", {})
        agent_data = data.get("agent", {})
        guardrail_data = data.get("guardrail", {})
        memory_data = data.get("memory", {})

        return cls(
            llm=LLMConfig(
                provider=llm_data.get("provider", "openai"),
                model=llm_data.get("model", "gpt-4o"),
                api_key=llm_data.get("api_key"),
                base_url=llm_data.get("base_url"),
                temperature=llm_data.get("temperature", 0.2),
                max_tokens=llm_data.get("max_tokens", 4096),
            ),
            agent=AgentConfig(
                max_react_steps=agent_data.get("max_react_steps", 3),
                max_plan_steps=agent_data.get("max_plan_steps", 7),
                context_window=agent_data.get("context_window", 8000),
                auto_confirm=agent_data.get("auto_confirm", False),
            ),
            guardrail=GuardrailConfig(
                enabled=guardrail_data.get("enabled", True),
                timeout=guardrail_data.get("timeout", 30),
            ),
            memory=MemoryConfig(
                long_term_path=memory_data.get("long_term_path", "~/.iterm_agent/memory.json"),
                max_facts=memory_data.get("max_facts", 50),
            ),
        )


def load_config(path: str | Path | None = None) -> AppConfig:
    """加载配置文件。

    查找顺序：
    1. 显式传入的 path
    2. ~/.iterm_agent/config.yaml
    3. 项目内 config/default.yaml（开发用）

    如果都不存在，返回默认配置。
    """
    candidates = []
    if path:
        candidates.append(Path(path))
    else:
        candidates.append(Path.home() / ".iterm_agent" / "config.yaml")
        candidates.append(Path(__file__).parent.parent / "config" / "default.yaml")

    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return AppConfig.from_dict(data)

    # 无配置文件，返回默认
    return AppConfig()

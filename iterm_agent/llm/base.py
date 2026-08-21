"""LLM Provider 抽象基类与响应数据类。"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable


@dataclass
class LLMResponse:
    """统一的 LLM 响应结构。"""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class StreamChunk:
    """流式输出的单个 chunk。"""
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    is_final: bool = False


# 流式 token 回调类型：接收增量文本
TokenCallback = Callable[[str], None]


class LLMProvider(abc.ABC):
    """LLM 提供者抽象基类。"""

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """非流式对话。"""
        ...

    @abc.abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        on_token: TokenCallback | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """流式对话。

        每收到一个 token 就调用 on_token(delta_text)，
        最终返回完整的 LLMResponse（含 content 和 tool_calls）。
        """
        ...

    @abc.abstractmethod
    async def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """强制 JSON 输出。"""
        ...

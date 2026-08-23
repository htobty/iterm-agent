"""Anthropic Provider：原生 Anthropic Messages API 实现。"""

from __future__ import annotations

import logging
from typing import Any

from iterm_agent.llm.base import LLMProvider, LLMResponse, TokenCallback

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 原生接口。"""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        forced_temperature: float | None = None,
        **kwargs: Any,
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "使用 Anthropic provider 需要安装 anthropic 包：pip install anthropic"
            )
        self.model = model
        self.forced_temperature = forced_temperature
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """将 OpenAI 格式消息转换为 Anthropic 格式。

        返回 (system_text, anthropic_messages)。
        """
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")

            if role == "system":
                if content:
                    system_parts.append(content)
                continue

            if role == "assistant":
                # 处理 tool_calls
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    blocks: list[dict[str, Any]] = []
                    if content:
                        blocks.append({"type": "text", "text": content})
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        import json
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            args = json.loads(args)
                        blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args,
                        })
                    converted.append({"role": "assistant", "content": blocks})
                else:
                    converted.append({"role": "assistant", "content": content or ""})

            elif role == "tool":
                # Anthropic 的 tool result 是 user 消息中的 tool_result block
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content or "",
                    }],
                })

            elif role == "user":
                converted.append({"role": "user", "content": content or ""})

        return "\n".join(system_parts), converted

    def _convert_tools(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """将 OpenAI 格式工具定义转换为 Anthropic 格式。"""
        if not tools:
            return None
        converted = []
        for tool in tools:
            func = tool.get("function", {})
            converted.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return converted

    def _parse_response(self, response: Any) -> LLMResponse:
        """解析 Anthropic 响应为统一格式。"""
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "function_name": block.name,
                    "arguments": block.input,
                })

        return LLMResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            raw=response,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        system_text, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        temp = self.forced_temperature if self.forced_temperature is not None else temperature

        params: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temp,
        }
        if system_text:
            params["system"] = system_text
        if anthropic_tools:
            params["tools"] = anthropic_tools

        response = await self.client.messages.create(**params)
        return self._parse_response(response)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        on_token: TokenCallback | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        system_text, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        temp = self.forced_temperature if self.forced_temperature is not None else temperature

        params: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temp,
        }
        if system_text:
            params["system"] = system_text
        if anthropic_tools:
            params["tools"] = anthropic_tools

        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        # 用于累积流式 tool_use 的 input JSON
        current_tool: dict[str, Any] | None = None
        current_tool_json = ""

        async with self.client.messages.stream(**params) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool = {
                            "id": event.content_block.id,
                            "function_name": event.content_block.name,
                        }
                        current_tool_json = ""
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        text = event.delta.text
                        content_parts.append(text)
                        if on_token:
                            on_token(text)
                    elif event.delta.type == "input_json_delta":
                        current_tool_json += event.delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool is not None:
                        import json
                        try:
                            current_tool["arguments"] = json.loads(current_tool_json) if current_tool_json else {}
                        except json.JSONDecodeError:
                            current_tool["arguments"] = {}
                        tool_calls.append(current_tool)
                        current_tool = None

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            raw=None,
        )

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """强制 JSON 输出（通过在 system 中要求 JSON）。"""
        import json

        # 在消息前加一条要求 JSON 的指令
        json_instruction = {"role": "user", "content": "请以纯 JSON 格式回复，不要包含任何其他文字。"}
        augmented = messages + [json_instruction]

        response = await self.chat(
            messages=augmented,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 块
            text = response.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"error": "无法解析 JSON 输出", "raw": response.content}

"""OpenAI 兼容 Provider（支持 OpenAI / Azure / vLLM / Moonshot / 任意兼容接口）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from iterm_agent.llm.base import LLMProvider, LLMResponse, TokenCallback

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API Provider。"""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        forced_temperature: float | None = None,
        **kwargs: Any,
    ):
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.forced_temperature = forced_temperature

    def _get_temperature(self, temperature: float) -> float:
        if self.forced_temperature is not None:
            return self.forced_temperature
        return temperature

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._get_temperature(temperature),
            "max_tokens": max_tokens,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        resp = await self.client.chat.completions.create(**params)
        choice = resp.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "function_name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            raw=resp,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        on_token: TokenCallback | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """流式对话：逐 token 回调 on_token，最终返回完整响应。"""
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._get_temperature(temperature),
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        full_content = ""
        # 累积 tool_calls（流式中 tool_call 分多个 chunk 到达）
        tool_call_acc: dict[int, dict[str, Any]] = {}

        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 文本内容
            if delta.content:
                full_content += delta.content
                if on_token:
                    on_token(delta.content)

            # tool_calls 累积
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_call_acc:
                        tool_call_acc[idx] = {
                            "id": tc_delta.id or "",
                            "function_name": "",
                            "arguments_str": "",
                        }
                    if tc_delta.id:
                        tool_call_acc[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_call_acc[idx]["function_name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_call_acc[idx]["arguments_str"] += tc_delta.function.arguments

        # 解析累积的 tool_calls
        tool_calls = []
        for idx in sorted(tool_call_acc.keys()):
            tc = tool_call_acc[idx]
            try:
                args = json.loads(tc["arguments_str"]) if tc["arguments_str"] else {}
            except json.JSONDecodeError:
                args = {"raw": tc["arguments_str"]}
            tool_calls.append({
                "id": tc["id"],
                "function_name": tc["function_name"],
                "arguments": args,
            })

        return LLMResponse(
            content=full_content,
            tool_calls=tool_calls,
        )

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._get_temperature(temperature),
            "max_tokens": max_tokens,
        }

        try:
            params["response_format"] = {"type": "json_object"}
            resp = await self.client.chat.completions.create(**params)
        except Exception as e:
            if "response_format" in str(e) or "json_object" in str(e):
                logger.debug(f"response_format 不支持，降级为 prompt 约束")
                params.pop("response_format", None)
                constrained = [m.copy() for m in messages]
                for i, m in enumerate(constrained):
                    if m["role"] == "system":
                        constrained[i] = {
                            "role": "system",
                            "content": m["content"] + "\n\n你必须只输出合法 JSON，不要包含 markdown 代码块。",
                        }
                        break
                params["messages"] = constrained
                resp = await self.client.chat.completions.create(**params)
            else:
                raise

        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

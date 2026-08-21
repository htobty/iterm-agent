"""工具注册表：统一管理所有 Agent 可用工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class Tool:
    """单个工具的定义。"""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Coroutine[Any, Any, str]]

    def to_function_schema(self) -> dict[str, Any]:
        """转为 OpenAI Function Calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        """返回所有工具的 Function Calling schema。"""
        return [t.to_function_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """执行指定工具，返回字符串结果。"""
        tool = self._tools.get(name)
        if tool is None:
            return f"[ERROR] 未知工具: {name}"
        try:
            result = await tool.handler(**params)
            return result
        except Exception as e:
            return f"[ERROR] 工具 {name} 执行异常: {type(e).__name__}: {e}"


def build_default_tools() -> ToolRegistry:
    """构建默认工具集。"""
    from iterm_agent.tools.run_command import run_command_tool

    reg = ToolRegistry()
    reg.register(run_command_tool)
    return reg

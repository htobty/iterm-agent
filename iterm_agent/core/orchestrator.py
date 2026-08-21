"""Orchestrator：Agent 调度器（精简版，直接走 ReAct 执行器）。"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from iterm_agent.core.context import AgentContext
from iterm_agent.core.executor import Executor, ConfirmCallback
from iterm_agent.core.router import InputRouter
from iterm_agent.guardrail.engine import GuardrailEngine, GuardrailAction
from iterm_agent.llm.base import LLMProvider, TokenCallback
from iterm_agent.memory.long_term import LongTermStore
from iterm_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class Orchestrator:
    """Agent 调度器。"""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        guardrail: GuardrailEngine | None = None,
        router: InputRouter | None = None,
        long_term: LongTermStore | None = None,
        max_react_steps: int = 3,
        auto_confirm: bool = False,
        confirm_callback: ConfirmCallback | None = None,
    ):
        self.llm = llm
        self.tools = tools
        self.guardrail = guardrail or GuardrailEngine()
        self.router = router or InputRouter()
        self.auto_confirm = auto_confirm
        self.confirm_callback = confirm_callback

        self.long_term = long_term or LongTermStore()

        self.executor = Executor(
            llm=llm,
            tools=tools,
            guardrail=self.guardrail,
            max_steps=max_react_steps,
            auto_confirm=auto_confirm,
            confirm_callback=confirm_callback,
        )
        self.ctx = AgentContext()

    async def handle(
        self,
        user_input: str,
        on_token: TokenCallback | None = None,
        skip_planner: bool = False,
    ) -> str:
        """处理用户输入，返回结果。"""
        logger.info(f"User input: {user_input}")

        if skip_planner:
            result = await self._handle_agent(user_input, on_token=on_token)
        else:
            route = self.router.route(user_input)
            logger.info(f"Route: {route.target} ({route.reason})")

            if route.target == "shell":
                result = await self._handle_shell(route.cleaned_input)
            else:
                result = await self._handle_agent(route.cleaned_input, on_token=on_token)

        return result

    async def _handle_shell(self, command: str) -> str:
        guard_result = self.guardrail.check(command)

        if guard_result.action == GuardrailAction.BLOCK:
            return f"\033[31m[已阻止]\033[0m {guard_result.reason}\n命令: {command}"

        if guard_result.needs_confirmation:
            confirmed = await self._confirm(command, guard_result.reason)
            if not confirmed:
                return f"\033[33m[已取消]\033[0m 用户拒绝了操作。\n命令: {command}"

        timeout = self.guardrail.get_timeout(command)
        result = await self.tools.execute("run_command", {
            "command": command,
            "timeout": timeout,
        })
        return result

    async def _handle_agent(
        self,
        user_input: str,
        on_token: TokenCallback | None = None,
    ) -> str:
        logger.info("→ Direct Mode (streaming)")
        result = await self.executor.execute(user_input, self.ctx, on_token=on_token)
        return result

    async def _confirm(self, command: str, reason: str) -> bool:
        if self.auto_confirm:
            return True
        if self.confirm_callback is not None:
            return await self.confirm_callback(command, reason)
        return False

    def reset(self) -> None:
        self.ctx.clear()

"""Executor：ReAct 循环核心执行器（流式输出版）。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from iterm_agent.core.context import AgentContext
from iterm_agent.guardrail.engine import GuardrailEngine, GuardrailAction, GuardrailResult
from iterm_agent.guardrail.intent_guard import IntentGuard
from iterm_agent.llm.base import LLMProvider, TokenCallback
from iterm_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个 macOS 终端执行助手。用户用自然语言描述需求，你通过调用工具完成任务。

当前环境：macOS, zsh, 已安装 Homebrew。

规则：
1. 如果用户只是打招呼、闲聊、问你是谁等非任务类输入，直接友好回复，不要调用任何工具
2. 只有用户明确要求执行操作（安装、查看、创建、修改等）时，才调用工具
3. 每次只调用一个工具
4. 如果任务已完成，直接输出最终结果（不调用工具）
5. 命令必须安全、精确，不要猜测
6. 不要执行危险操作（如 rm -rf /、格式化磁盘等），系统会拦截
7. 当用户明确要求记住某事（如"记住xxx"、"帮我记一下xxx"、"remember xxx"）时，调用 remember 工具
8. 你可以使用 ssh 连接局域网内的远程机器执行操作（如 ssh user@192.168.x.x "命令"），如果用户提到远程机器或局域网设备
"""

# 确认回调类型
ConfirmCallback = Callable[[str, str], Awaitable[bool]]


class Executor:
    """ReAct 执行器（流式输出 + 安全护栏）。

    核心循环：
    1. 将上下文 + 用户输入发给 LLM（流式）
    2. LLM 返回 tool_call → 护栏检查 → 执行工具 → 将结果追加到上下文
    3. 重复直到 LLM 不再调用工具（表示任务完成）

    流式输出：
    - 最终回复（无 tool_call）时，逐 token 通过 on_token 回调输出
    - 中间步骤（有 tool_call）时不输出 token，只记录
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        guardrail: GuardrailEngine | None = None,
        max_steps: int = 3,
        auto_confirm: bool = False,
        confirm_callback: ConfirmCallback | None = None,
    ):
        self.llm = llm
        self.tools = tools
        self.guardrail = guardrail or GuardrailEngine()
        self.intent_guard = IntentGuard()
        self.max_steps = max_steps
        self.auto_confirm = auto_confirm
        self.confirm_callback = confirm_callback

    async def execute(
        self,
        user_input: str,
        ctx: AgentContext,
        on_token: TokenCallback | None = None,
    ) -> str:
        """执行 ReAct 循环，返回最终结果文本。带整体超时保护。"""
        try:
            return await asyncio.wait_for(
                self._execute_inner(user_input, ctx, on_token),
                timeout=300,  # 整体 5 分钟超时
            )
        except asyncio.TimeoutError:
            logger.warning("整体执行超时（300s）")
            return "[TIMEOUT] 任务执行超时（5分钟），已终止。请简化指令后重试。"

    async def _execute_inner(
        self,
        user_input: str,
        ctx: AgentContext,
        on_token: TokenCallback | None = None,
    ) -> str:
        """ReAct 循环核心逻辑。"""
        messages = ctx.build_messages(SYSTEM_PROMPT, user_input)
        tool_schemas = self.tools.get_schemas()
        last_command: str | None = None  # 只拦截连续重复

        for step in range(self.max_steps):
            logger.info(f"ReAct step {step + 1}/{self.max_steps}")

            # 使用流式调用
            response = await self.llm.chat_stream(
                messages=messages,
                tools=tool_schemas,
                temperature=0.2,
                on_token=on_token,  # 只有最终回复时 LLM 才输出纯文本
            )

            # LLM 返回工具调用
            if response.has_tool_calls:
                # 构建标准 tool calling 格式的 assistant 消息
                tool_calls_payload = []
                for tc in response.tool_calls:
                    tool_calls_payload.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function_name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    })
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls_payload,
                })

                for tc in response.tool_calls:
                    func_name = tc["function_name"]
                    params = tc["arguments"]
                    logger.info(f"  Tool call: {func_name}({params})")

                    # 护栏检查
                    if func_name == "run_command":
                        command = params.get("command", "")

                        # 连续重复命令检测（只拦截上一步刚执行过的相同命令，
                        # 中间有其他命令执行过则放行，因为状态可能已变化）
                        cmd_key = command.strip()
                        if cmd_key == last_command:
                            observation = (
                                f"[REPEATED] 该命令与上一步完全相同，结果不会改变。"
                                f"请换一种方式完成任务，或直接向用户报告当前结果。"
                            )
                            logger.warning(f"  REPEATED (consecutive): {cmd_key[:80]}")
                        else:
                            last_command = cmd_key

                            # 意图校验：防止 prompt injection
                            intent_passed, intent_reason = self.intent_guard.check(user_input, command)
                            if not intent_passed:
                                observation = (
                                    f"[INTENT_BLOCKED] {intent_reason}\n"
                                    f"命令: {command}\n"
                                    f"该命令与用户意图不匹配，已拒绝执行。"
                                    f"请根据用户实际意图重新生成命令。"
                                )
                                logger.warning(f"  INTENT_BLOCKED: {intent_reason}")
                            else:
                                guard_result = self.guardrail.check(command)

                                if guard_result.action == GuardrailAction.BLOCK:
                                    observation = (
                                        f"[BLOCKED] {guard_result.reason}\n"
                                        f"命令: {command}\n"
                                        f"请换一个安全的方案，或告知用户该操作被禁止。"
                                    )
                                    logger.warning(f"  BLOCKED: {guard_result.reason}")
                                elif guard_result.needs_confirmation:
                                    confirmed = await self._confirm(command, guard_result.reason)
                                    if not confirmed:
                                        observation = (
                                            f"[REJECTED] 用户拒绝了该操作。\n"
                                            f"命令: {command}\n"
                                            f"请询问用户是否需要替代方案。"
                                        )
                                    else:
                                        observation = await self.tools.execute(func_name, params)
                                else:
                                    observation = await self.tools.execute(func_name, params)
                    else:
                        observation = await self.tools.execute(func_name, params)

                    logger.info(f"  Observation: {observation[:200]}")

                    # 标准 tool 消息格式
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": observation,
                    })
                continue

            # LLM 返回纯文本（任务完成）
            final_answer = response.content
            ctx.record_exchange(user_input, final_answer)
            return final_answer

        # 循环结束：如果最后一步是工具调用，额外给 LLM 一次机会输出总结
        if messages and messages[-1]["role"] == "tool":
            logger.info("Max steps reached, requesting final summary from LLM")
            try:
                final_response = await self.llm.chat_stream(
                    messages=messages,
                    tools=None,  # 不带 tools，强制纯文本输出
                    temperature=0.2,
                    on_token=on_token,
                )
                final_answer = final_response.content
                ctx.record_exchange(user_input, final_answer)
                return final_answer
            except Exception as e:
                logger.warning(f"Final summary failed: {e}")

        return f"[MAX_STEPS] 已执行 {self.max_steps} 步，任务可能未完成。请重试或简化指令。"

    async def _confirm(self, command: str, reason: str) -> bool:
        """确认流程。"""
        if self.auto_confirm:
            return True
        if self.confirm_callback is not None:
            return await self.confirm_callback(command, reason)
        return False

"""Agent 上下文：管理对话历史和运行状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Agent 运行上下文，贯穿整个会话。

    Attributes:
        messages: 近期对话消息（OpenAI 格式）
        summary: 早期对话的压缩摘要（由 LLM 生成）
        long_term_memories: 检索到的长期记忆条目
        working_dir: 当前工作目录
        session_id: 会话标识
        metadata: 附加元数据
    """

    messages: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    long_term_memories: list[str] = field(default_factory=list)
    working_dir: str = ""
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_system(self, content: str) -> None:
        self.messages.insert(0, {"role": "system", "content": content})

    def build_messages(self, system_prompt: str, user_input: str) -> list[dict[str, str]]:
        """构建发送给 LLM 的完整消息列表。

        结构：
        [system: 基础 prompt]
        [system: 会话摘要（如果有）]
        [system: 长期记忆（如果有）]
        [近期消息...]
        [user: 当前输入]
        """
        msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # 注入会话摘要（早期对话的压缩）
        if self.summary:
            msgs.append({
                "role": "system",
                "content": f"以下是本次会话早期对话的摘要，请基于此保持上下文连贯：\n{self.summary}",
            })

        # 注入长期记忆
        if self.long_term_memories:
            mem_text = "\n".join(f"- {m}" for m in self.long_term_memories)
            msgs.append({
                "role": "system",
                "content": f"历史经验（与当前任务相关）：\n{mem_text}",
            })

        # 近期消息
        msgs.extend(self.messages)

        # 当前用户输入
        msgs.append({"role": "user", "content": user_input})

        return msgs

    def record_exchange(self, user_input: str, assistant_output: str) -> None:
        """记录一轮交互到历史。"""
        self.add_user(user_input)
        self.add_assistant(assistant_output)

    def clear(self) -> None:
        self.messages.clear()
        self.summary = ""
        self.long_term_memories.clear()

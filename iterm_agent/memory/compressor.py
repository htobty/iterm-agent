"""上下文压缩：当会话消息超长时，调用 LLM 将旧消息压缩为摘要。

策略：
- 保留最近 N 轮完整消息（默认 6 轮 = 12 条）
- 更早的消息压缩为一段摘要文本
- 摘要追加到已有摘要后面（增量压缩）
"""

from __future__ import annotations

import logging
from typing import Any

from iterm_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# 保留最近多少条消息不压缩（6 轮 = 12 条）
KEEP_RECENT = 12

# 压缩触发阈值：消息数超过此值时触发压缩
COMPRESS_THRESHOLD = 16

COMPRESS_SYSTEM_PROMPT = """\
你是一个对话摘要器。将以下对话历史压缩为简洁的摘要，保留关键信息：
- 用户的目标和需求
- 已执行的操作和结果
- 重要的技术决策
- 未完成的事项

要求：
- 用中文输出
- 控制在 200 字以内
- 不要遗漏关键上下文
- 直接输出摘要文本，不要加任何前缀或格式
"""


async def compress_messages(
    llm: LLMProvider,
    messages: list[dict[str, str]],
    existing_summary: str = "",
) -> str:
    """将消息列表压缩为摘要。

    Args:
        llm: LLM Provider
        messages: 要压缩的消息列表（OpenAI 格式）
        existing_summary: 已有的摘要（增量压缩时追加）

    Returns:
        压缩后的摘要文本
    """
    if not messages:
        return existing_summary

    # 构建压缩输入
    conversation = ""
    for msg in messages:
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"]
        # 截断过长的单条消息
        if len(content) > 500:
            content = content[:500] + "..."
        conversation += f"{role}: {content}\n"

    user_prompt = f"请压缩以下对话：\n\n{conversation}"
    if existing_summary:
        user_prompt = f"已有摘要：\n{existing_summary}\n\n新增对话：\n{conversation}\n\n请合并为一段完整摘要。"

    try:
        response = await llm.chat(
            messages=[
                {"role": "system", "content": COMPRESS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        summary = response.content.strip()
        logger.info(f"Compressed {len(messages)} messages → {len(summary)} chars summary")
        return summary
    except Exception as e:
        logger.warning(f"Compression failed: {e}, falling back to truncation")
        # 降级：简单截断
        fallback_parts = []
        for msg in messages:
            if msg["role"] == "user":
                fallback_parts.append(f"用户: {msg['content'][:60]}")
            else:
                fallback_parts.append(f"结果: {msg['content'][:40]}")
        fallback = " | ".join(fallback_parts[-8:])
        return f"{existing_summary}\n{fallback}" if existing_summary else fallback


def should_compress(messages: list[dict[str, str]]) -> bool:
    """判断是否需要压缩。"""
    return len(messages) > COMPRESS_THRESHOLD


def split_for_compress(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """将消息分为 [待压缩的旧消息, 保留的近期消息]。

    确保分割点不会在 user/assistant 对中间断开。
    """
    if len(messages) <= KEEP_RECENT:
        return [], messages

    split_point = len(messages) - KEEP_RECENT

    # 确保分割点在 user 消息之前（即 assistant 消息之后）
    while split_point > 0 and messages[split_point]["role"] == "assistant":
        split_point -= 1

    return messages[:split_point], messages[split_point:]

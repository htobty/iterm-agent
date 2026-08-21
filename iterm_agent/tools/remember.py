"""remember 工具：将用户要求记住的内容写入长期记忆。"""

from __future__ import annotations

from iterm_agent.tools.registry import Tool


async def _remember_handler(content: str) -> str:
    """写入长期记忆。"""
    from iterm_agent.memory.long_term import LongTermStore
    import os

    store = LongTermStore(
        path=os.path.expanduser("~/.iterm_agent/memory.json"),
        max_entries=50,
    )
    store.add(content)
    return f"[OK] 已记住: {content}"


remember_tool = Tool(
    name="remember",
    description="将用户要求记住的信息写入长期记忆，跨会话持久化。当用户说'记住xxx'、'帮我记一下xxx'、'remember xxx'等明确要求记住时调用",
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要记住的内容，应简洁明确",
            },
        },
        "required": ["content"],
    },
    handler=_remember_handler,
)

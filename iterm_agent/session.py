"""会话持久化：基于 iTerm2 窗口 ID 的独立会话管理。

每个 iTerm2 窗口拥有独立会话，历史消息持久化到本地文件。
不限制、不清理，上下文超长时由上层进行 LLM 压缩。

存储路径：~/.iterm_agent/sessions/<session_id>.json
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Session:
    """单个会话。"""
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # 压缩后的早期对话摘要（由 LLM 生成）
    summary: str = ""
    # 近期完整消息（OpenAI 格式）
    messages: list[dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()

    def add_exchange(self, user_input: str, assistant_output: str) -> None:
        self.add_message("user", user_input)
        self.add_message("assistant", assistant_output)

    @property
    def round_count(self) -> int:
        """对话轮数（user+assistant 为一轮）。"""
        return len(self.messages) // 2


class SessionStore:
    """会话存储：加载/保存/管理会话文件。"""

    def __init__(self, base_dir: str = "~/.iterm_agent/sessions"):
        self.base_dir = Path(os.path.expanduser(base_dir))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_session_id(self) -> str:
        """获取当前会话 ID。

        优先级：
        1. ITERM_SESSION_ID（iTerm2 自动设置）
        2. TERM_SESSION_ID（其他终端）
        3. 固定 "default"
        """
        sid = os.environ.get("ITERM_SESSION_ID") or os.environ.get("TERM_SESSION_ID")
        if sid:
            # 替换特殊字符为下划线，确保文件名安全
            return sid.replace(":", "_").replace("/", "_")
        return "default"

    def _path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def load(self, session_id: str | None = None) -> Session:
        """加载会话，不存在则创建空会话。"""
        if session_id is None:
            session_id = self.get_session_id()

        path = self._path(session_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
                return Session(
                    session_id=data.get("session_id", session_id),
                    created_at=data.get("created_at", time.time()),
                    updated_at=data.get("updated_at", time.time()),
                    summary=data.get("summary", ""),
                    messages=data.get("messages", []),
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # 不存在或损坏，创建新会话
        return Session(session_id=session_id)

    def save(self, session: Session) -> None:
        """保存会话到文件（带文件锁）。"""
        path = self._path(session.session_id)
        data = {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "summary": session.summary,
            "messages": session.messages,
        }
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话（调试用）。"""
        sessions = []
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                sessions.append({
                    "id": data.get("session_id", f.stem),
                    "updated_at": data.get("updated_at", 0),
                    "rounds": len(data.get("messages", [])) // 2,
                    "has_summary": bool(data.get("summary")),
                })
            except (json.JSONDecodeError, TypeError):
                continue
        return sessions

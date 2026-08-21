"""长期记忆存储：跨会话持久化。

使用 JSON 文件存储，支持：
- 添加/删除记忆条目
- 关键词检索（简单文本匹配）
- 容量限制（超出时淘汰最旧的）
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    """单条长期记忆。"""
    content: str
    id: str = ""
    keywords: list[str] = field(default_factory=list)
    created_at: float = 0.0
    access_count: int = 0
    last_accessed: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = f"mem_{int(time.time() * 1000)}"
        if not self.created_at:
            self.created_at = time.time()


class LongTermStore:
    """长期记忆存储（JSON 文件持久化）。

    特点：
    - 简单关键词检索（无向量数据库依赖）
    - 容量限制，超出时淘汰最久未访问的
    - 线程安全（单线程使用场景下无需锁）
    """

    def __init__(self, path: str = "~/.iterm_agent/memory.json", max_entries: int = 50):
        self.path = Path(os.path.expanduser(path))
        self.max_entries = max_entries
        self._entries: list[MemoryEntry] = []
        self._load()

    def _load(self) -> None:
        """从文件加载记忆。"""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = [
                    MemoryEntry(**entry) for entry in data.get("entries", [])
                ]
            except (json.JSONDecodeError, TypeError) as e:
                # 文件损坏，备份后重置
                backup = self.path.with_suffix(".bak")
                try:
                    self.path.rename(backup)
                except OSError:
                    pass
                self._entries = []

    def _save(self) -> None:
        """持久化到文件。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [asdict(e) for e in self._entries],
            "updated_at": time.time(),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, content: str, keywords: list[str] | None = None) -> MemoryEntry:
        """添加一条记忆。"""
        entry = MemoryEntry(
            content=content,
            keywords=keywords or self._extract_keywords(content),
        )
        self._entries.append(entry)

        # 超出容量时淘汰最久未访问的
        if len(self._entries) > self.max_entries:
            self._evict()

        self._save()
        return entry

    def retrieve(self, query: str, top_k: int = 3) -> list[MemoryEntry]:
        """根据查询检索相关记忆。

        简单策略：关键词匹配 + 访问频率加权。
        """
        if not self._entries:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries:
            score = 0.0

            # 关键词匹配
            entry_keywords = set(kw.lower() for kw in entry.keywords)
            if query_words & entry_keywords:
                score += 2.0

            # 内容包含查询词
            content_lower = entry.content.lower()
            for word in query_words:
                if len(word) > 1 and word in content_lower:
                    score += 1.0

            # 访问频率加分
            score += min(entry.access_count * 0.1, 1.0)

            # 时间衰减（越新越好）
            age_hours = (time.time() - entry.created_at) / 3600
            score += max(0, 1.0 - age_hours / 168)  # 7 天内有效

            if score > 0:
                scored.append((score, entry))

        # 按分数排序
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:top_k]]

        # 更新访问计数
        for entry in results:
            entry.access_count += 1
            entry.last_accessed = time.time()

        if results:
            self._save()

        return results

    def remove(self, entry_id: str) -> bool:
        """删除一条记忆。"""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def clear(self) -> None:
        """清空所有记忆。"""
        self._entries.clear()
        self._save()

    def __len__(self) -> int:
        return len(self._entries)

    def _evict(self) -> None:
        """淘汰最久未访问的条目。"""
        if len(self._entries) <= self.max_entries:
            return
        # 按 last_accessed 排序，删除最旧的
        self._entries.sort(key=lambda e: e.last_accessed or e.created_at)
        excess = len(self._entries) - self.max_entries
        self._entries = self._entries[excess:]

    def _extract_keywords(self, text: str) -> list[str]:
        """简单关键词提取：取长度 > 1 的词。"""
        words = text.lower().split()
        # 过滤常见停用词
        stop_words = {"the", "a", "an", "is", "are", "was", "were",
                      "in", "on", "at", "to", "for", "of", "and", "or",
                      "帮我", "请", "的", "了", "是", "在"}
        return [w for w in words if len(w) > 1 and w not in stop_words][:10]

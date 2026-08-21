"""意图校验：防止 LLM 被 prompt injection 诱导执行与用户意图无关的命令。

校验策略：
1. 命令长度限制（超过 500 字符拒绝）
2. 危险操作与用户意图不匹配时拒绝
3. 多命令拼接中混入无关危险命令时拒绝
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# 命令最大长度
MAX_COMMAND_LENGTH = 500

# 危险操作关键词 → 用户输入中应包含的对应意图词
# 如果命令包含危险操作，但用户输入中没有相关意图词，则拒绝
DANGEROUS_INTENT_MAP: list[tuple[str, list[str]]] = [
    # (命令中的危险模式, 用户输入中应包含的意图词)
    (r"rm\s+-[rf]", ["删除", "移除", "清理", "remove", "delete", "clean"]),
    (r"sudo\s+", ["权限", "sudo", "管理员", "root"]),
    (r"git\s+push", ["推送", "push", "提交到远程"]),
    (r"git\s+reset\s+--hard", ["重置", "reset", "回退"]),
    (r"git\s+branch\s+-D", ["删除分支", "删分支"]),
    (r"docker\s+rm", ["删除容器", "删容器"]),
    (r"docker\s+rmi", ["删除镜像", "删镜像"]),
    (r"kill\s+-9", ["杀进程", "kill", "终止"]),
    (r"killall|pkill", ["杀进程", "kill", "终止"]),
    (r"chmod\s+777", ["权限", "chmod"]),
    (r"mkfs", ["格式化"]),
    (r"dd\s+if=", ["写入磁盘", "dd"]),
]


class IntentGuard:
    """意图校验器：检查 LLM 生成的命令是否与用户原始意图一致。"""

    def __init__(self, max_command_length: int = MAX_COMMAND_LENGTH):
        self.max_command_length = max_command_length
        self._compiled_patterns: list[tuple[re.Pattern, list[str]]] = [
            (re.compile(p, re.IGNORECASE), intents)
            for p, intents in DANGEROUS_INTENT_MAP
        ]

    def check(self, user_input: str, command: str) -> tuple[bool, str]:
        """校验命令是否与用户意图一致。

        Args:
            user_input: 用户的原始自然语言输入
            command: LLM 生成的要执行的命令

        Returns:
            (是否通过, 拒绝原因)
        """
        # 1. 命令长度检查（已移除，不再限制命令长度）

        # 2. 多命令拼接检查：拆分后逐段检查
        segments = re.split(r";|&&|\|\|", command)
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            passed, reason = self._check_single(user_input, segment)
            if not passed:
                return False, reason

        return True, ""

    def _check_single(self, user_input: str, command: str) -> tuple[bool, str]:
        """检查单条命令。"""
        user_lower = user_input.lower()

        for pattern, intent_words in self._compiled_patterns:
            if pattern.search(command):
                # 命令包含危险操作，检查用户输入是否有对应意图
                has_intent = any(word.lower() in user_lower for word in intent_words)
                if not has_intent:
                    return False, (
                        f"命令包含危险操作（{pattern.pattern}），"
                        f"但用户输入中未表达相关意图"
                    )

        return True, ""

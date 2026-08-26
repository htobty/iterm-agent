"""Input Router：区分普通 shell 命令和自然语言指令。

路由策略（优先级从高到低）：
1. 以 /ai 或 ai 开头 → 强制进入 Agent
2. 包含中文且不是已知命令 → 进入 Agent
3. 匹配已知命令白名单 → 直接执行 shell
4. 其他 → 直接执行 shell（不拦截）
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RouteResult:
    """路由结果。"""
    target: str  # "agent" 或 "shell"
    reason: str = ""
    cleaned_input: str = ""  # 去掉触发前缀后的实际输入


class InputRouter:
    """输入路由器。

    将用户输入分为两类：
    - shell: 普通命令，直接执行
    - agent: 自然语言指令，交给 Agent 处理
    """

    # 强制触发 Agent 的前缀
    AGENT_PREFIXES = ("/ai", "ai ", "/agent", "agent ")

    # 已知 shell 命令白名单（首词匹配）
    COMMAND_WHITELIST = frozenset({
        # 基础
        "ls", "cd", "pwd", "echo", "cat", "head", "tail", "grep", "find",
        "mkdir", "rm", "cp", "mv", "touch", "ln", "chmod", "chown",
        "which", "whoami", "date", "env", "export", "set", "unset",
        "man", "help", "type", "alias", "unalias",
        # 包管理
        "brew", "pip", "pip3", "npm", "npx", "yarn", "pnpm",
        "cargo", "go", "gem", "apt", "apt-get", "yum", "dnf",
        # 版本控制
        "git", "svn", "hg",
        # 网络
        "curl", "wget", "ssh", "scp", "rsync", "ping", "nslookup", "dig",
        # 容器/编排
        "docker", "kubectl", "helm", "terraform",
        # 构建
        "make", "cmake", "mvn", "gradle", "webpack", "vite",
        # 解释器
        "python", "python3", "node", "ruby", "perl", "bash", "zsh", "sh",
        # 系统
        "ps", "top", "htop", "kill", "killall", "pkill", "lsof",
        "df", "du", "free", "uptime", "systemctl", "launchctl",
        # 编辑器
        "vim", "vi", "nano", "code", "subl",
        # 其他常用
        "tar", "zip", "unzip", "gzip", "gunzip", "xargs", "awk", "sed",
        "sort", "uniq", "wc", "cut", "tr", "tee", "diff", "patch",
        "open", "say", "screencapture", "osascript",
    })

    # 中文检测正则
    CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')

    # 中文自然语言特征词（问句/陈述句）
    NL_MARKERS = (
        "吗", "啊", "呢", "吧", "呀", "嘛", "哦", "哈",
        "怎么", "什么", "多少", "如何", "为什么", "哪", "谁",
        "能不能", "可以", "是否", "有没有", "是不是",
        "帮我", "请", "给我", "告诉我",
        "？", "?",
    )

    # 自然语言常见开头（增强判断）
    NL_HINTS = (
        "帮我", "请", "怎么", "如何", "能不能", "可以", "给我",
        "写一个", "写个", "创建", "安装", "配置", "检查", "查看",
        "把", "将", "运行", "执行", "删除", "修改", "添加",
    )

    def _is_chinese_nl(self, text: str) -> bool:
        """判断输入是否为中文自然语言（问句/陈述句）。"""
        if not self.CHINESE_RE.search(text):
            return False
        # 特征词匹配
        for marker in self.NL_MARKERS:
            if marker in text:
                return True
        # 中文字符占比 > 30%
        chinese_count = len(self.CHINESE_RE.findall(text))
        if len(text) > 0 and chinese_count / len(text) > 0.3:
            return True
        return False

    def route(self, text: str) -> RouteResult:
        """路由用户输入。

        Args:
            text: 用户原始输入

        Returns:
            RouteResult: 包含目标（agent/shell）和清理后的输入
        """
        stripped = text.strip()
        if not stripped:
            return RouteResult(target="shell", reason="空输入", cleaned_input="")

        # 1. 检查 Agent 前缀
        for prefix in self.AGENT_PREFIXES:
            if stripped.startswith(prefix):
                cleaned = stripped[len(prefix):].strip()
                return RouteResult(
                    target="agent",
                    reason=f"匹配前缀 '{prefix}'",
                    cleaned_input=cleaned,
                )

        first_word = stripped.split()[0]

        # 2. 路径检测：首词含路径分隔符或相对路径前缀 → 一定是命令
        if "/" in first_word or first_word.startswith("~") or first_word.startswith("."):
            return RouteResult(
                target="shell",
                reason=f"路径命令 '{first_word}'",
                cleaned_input=stripped,
            )

        # 3. 中文自然语言优先检测（即使首词碰巧是命令名）
        if self._is_chinese_nl(stripped):
            return RouteResult(
                target="agent",
                reason="中文自然语言",
                cleaned_input=stripped,
            )

        # 4. 检查首词是否在命令白名单中
        if first_word.lower() in self.COMMAND_WHITELIST:
            return RouteResult(
                target="shell",
                reason=f"已知命令 '{first_word}'",
                cleaned_input=stripped,
            )

        # 5. 匹配自然语言提示词
        for hint in self.NL_HINTS:
            if stripped.startswith(hint):
                return RouteResult(
                    target="agent",
                    reason=f"匹配自然语言提示 '{hint}'",
                    cleaned_input=stripped,
                )

        # 6. 默认：当作 shell 命令
        return RouteResult(
            target="shell",
            reason="默认 shell",
            cleaned_input=stripped,
        )

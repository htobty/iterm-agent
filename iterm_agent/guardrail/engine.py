"""安全护栏引擎：多层命令安全检查。

检查层级（优先级从高到低）：
1. 黑名单 → 直接拒绝执行
2. 危险模式 → 需要用户确认
3. 超时控制 → 限制命令执行时间
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class GuardrailAction(Enum):
    """护栏检查动作。"""
    ALLOW = "allow"                # 放行
    CONFIRM = "confirm"            # 需要用户确认
    BLOCK = "block"                # 直接拒绝


@dataclass
class GuardrailResult:
    """护栏检查结果。"""
    action: GuardrailAction
    reason: str = ""
    matched_pattern: str = ""

    @property
    def allowed(self) -> bool:
        return self.action != GuardrailAction.BLOCK

    @property
    def needs_confirmation(self) -> bool:
        return self.action == GuardrailAction.CONFIRM


class GuardrailEngine:
    """命令安全护栏引擎。

    使用方式：
        engine = GuardrailEngine()
        result = engine.check("rm -rf /")
        if result.action == GuardrailAction.BLOCK:
            print(f"拒绝: {result.reason}")
        elif result.needs_confirmation:
            # 询问用户
            ...
    """

    # ===== 黑名单：匹配即拒绝，不可执行 =====
    BLOCK_PATTERNS: list[tuple[str, str]] = [
        # (pattern, 描述)
        (r"rm\s+-rf\s+/", "删除根目录"),
        (r"rm\s+-rf\s+\*", "删除当前目录所有内容"),
        (r"rm\s+-rf\s+~", "删除用户目录"),
        (r"rm\s+-rf\s+\.?\s*$", "删除当前目录"),
        (r"mkfs", "格式化磁盘"),
        (r"dd\s+if=.*of=/dev/", "直接写入磁盘设备"),
        (r">\s*/dev/sd[a-z]", "覆盖磁盘设备"),
        (r"curl.*\|\s*(ba)?sh", "从网络下载并直接执行脚本"),
        (r"wget.*\|\s*(ba)?sh", "从网络下载并直接执行脚本"),
        (r"chmod\s+777\s+/", "修改根目录权限"),
        (r":\s*\(\)\s*\{.*\};\s*:", "fork bomb"),
        (r"shutdown", "关机"),
        (r"reboot", "重启"),
        (r"halt", "停止系统"),
        (r"init\s+0", "关机"),
        (r"init\s+6", "重启"),
    ]

    # ===== 需确认：匹配后询问用户 =====
    CONFIRM_PATTERNS: list[tuple[str, str]] = [
        (r"sudo\s+", "使用 sudo 提权"),
        (r"rm\s+-[rf]", "递归/强制删除"),
        (r"git\s+push", "推送代码到远程"),
        (r"git\s+push\s+.*--force", "强制推送（覆盖远程）"),
        (r"git\s+reset\s+--hard", "硬重置（丢失未提交更改）"),
        (r"git\s+branch\s+-D", "强制删除分支"),
        (r"git\s+clean\s+-[f]", "清理未跟踪文件"),
        (r"brew\s+install", "安装 Homebrew 包"),
        (r"brew\s+uninstall", "卸载 Homebrew 包"),
        (r"brew\s+upgrade", "升级 Homebrew 包"),
        (r"pip\s+install", "安装 Python 包"),
        (r"pip3\s+install", "安装 Python 包"),
        (r"pip\s+uninstall", "卸载 Python 包"),
        (r"npm\s+install", "安装 npm 包"),
        (r"npm\s+uninstall", "卸载 npm 包"),
        (r"npm\s+publish", "发布 npm 包"),
        (r"yarn\s+add", "安装 yarn 包"),
        (r"pnpm\s+add", "安装 pnpm 包"),
        (r"gem\s+install", "安装 Ruby 包"),
        (r"cargo\s+install", "安装 Rust 包"),
        (r"apt\s+install", "安装系统包"),
        (r"apt-get\s+install", "安装系统包"),
        (r"yum\s+install", "安装系统包"),
        (r"dnf\s+install", "安装系统包"),
        (r"docker\s+run", "运行 Docker 容器"),
        (r"docker\s+rm", "删除 Docker 容器"),
        (r"docker\s+rmi", "删除 Docker 镜像"),
        (r"docker\s+system\s+prune", "清理 Docker 资源"),
        (r"docker\s+volume\s+rm", "删除 Docker 卷"),
        (r"kubectl\s+delete", "删除 K8s 资源"),
        (r"kubectl\s+apply", "应用 K8s 配置"),
        (r"systemctl\s+(restart|stop|start|enable|disable)", "修改系统服务"),
        (r"launchctl\s+(unload|load|remove|bootout)", "修改 macOS 服务"),
        (r"kill\s+-9", "强制杀进程"),
        (r"killall", "杀所有匹配进程"),
        (r"pkill", "按名称杀进程"),
        (r"chmod\s+777", "开放所有权限"),
        (r"chown\s+.*\s+/", "修改系统目录所有者"),
        (r"ln\s+-sf\s+.*\s+/", "覆盖系统符号链接"),
        (r"crontab\s+", "修改定时任务"),
        (r"mv\s+.*\s+/dev/null", "移入 /dev/null（等效删除）"),
        (r">\s*/dev/null", "重定向到 /dev/null"),
        (r"osascript\s+-e", "执行 AppleScript"),
        (r"curl.*-o\s+/", "下载文件到系统目录"),
        (r"wget.*-O\s+/", "下载文件到系统目录"),
    ]

    def __init__(
        self,
        enabled: bool = True,
        timeout: int = 30,
        extra_block_patterns: list[str] | None = None,
        extra_confirm_patterns: list[str] | None = None,
    ):
        self.enabled = enabled
        self.timeout = timeout

        # 编译正则
        self._block_regexes: list[tuple[re.Pattern, str]] = [
            (re.compile(p, re.IGNORECASE), desc) for p, desc in self.BLOCK_PATTERNS
        ]
        self._confirm_regexes: list[tuple[re.Pattern, str]] = [
            (re.compile(p, re.IGNORECASE), desc) for p, desc in self.CONFIRM_PATTERNS
        ]

        # 用户自定义扩展
        if extra_block_patterns:
            for p in extra_block_patterns:
                self._block_regexes.append((re.compile(p, re.IGNORECASE), "用户自定义黑名单"))
        if extra_confirm_patterns:
            for p in extra_confirm_patterns:
                self._confirm_regexes.append((re.compile(p, re.IGNORECASE), "用户自定义确认项"))

    def check(self, command: str) -> GuardrailResult:
        """检查命令安全性。

        Args:
            command: 要执行的 shell 命令

        Returns:
            GuardrailResult: 包含动作（ALLOW/CONFIRM/BLOCK）和原因
        """
        if not self.enabled:
            return GuardrailResult(action=GuardrailAction.ALLOW)

        stripped = command.strip()
        if not stripped:
            return GuardrailResult(action=GuardrailAction.ALLOW)

        # 1. 检查黑名单
        for pattern, desc in self._block_regexes:
            if pattern.search(stripped):
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    reason=f"危险操作已阻止: {desc}",
                    matched_pattern=pattern.pattern,
                )

        # 2. 检查需确认模式
        for pattern, desc in self._confirm_regexes:
            if pattern.search(stripped):
                return GuardrailResult(
                    action=GuardrailAction.CONFIRM,
                    reason=f"需要确认: {desc}",
                    matched_pattern=pattern.pattern,
                )

        # 3. 放行
        return GuardrailResult(action=GuardrailAction.ALLOW)

    def get_timeout(self, command: str) -> int:
        """根据命令类型返回建议超时时间。

        某些命令天然需要更长时间（如安装、构建）。
        """
        long_running_patterns = [
            r"brew\s+install",
            r"pip\s+install",
            r"pip3\s+install",
            r"npm\s+install",
            r"cargo\s+build",
            r"make\s+install",
            r"docker\s+pull",
            r"git\s+clone",
        ]
        for p in long_running_patterns:
            if re.search(p, command, re.IGNORECASE):
                return max(self.timeout, 120)
        return self.timeout

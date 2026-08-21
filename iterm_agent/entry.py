"""iTerm2 入口：iTerm2 Python API 启动时自动加载。

使用方式：
将以下内容放入 ~/.config/iterm2/python_api.py：

    import sys, os
    sys.path.insert(0, os.path.expanduser("~/code/iterm-agent"))
    from iterm_agent.entry import start_agent
    import asyncio
    asyncio.run(start_agent())
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import termios
import tty
from typing import Any

from iterm_agent.config import load_config, AppConfig
from iterm_agent.core.orchestrator import Orchestrator
from iterm_agent.guardrail.engine import GuardrailEngine
from iterm_agent.llm.factory import create_provider
from iterm_agent.memory.long_term import LongTermStore
from iterm_agent.tools.registry import build_default_tools

logger = logging.getLogger(__name__)


def _read_tty_key() -> str:
    """从 /dev/tty 读取一个按键（raw 模式）。"""
    fd = os.open("/dev/tty", os.O_RDWR)
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        return ch.decode("utf-8", errors="replace")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        os.close(fd)


def _write_tty(text: str) -> None:
    """写入 /dev/tty。"""
    fd = os.open("/dev/tty", os.O_WRONLY)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


async def cli_confirm_callback(command: str, reason: str) -> bool:
    """终端确认交互：rich Panel 显示命令，按 Enter 确认，其他键取消。"""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    # 先暂停 stdout 输出，确保 tty 交互干净
    console = Console()

    # 命令用 bash 语法高亮
    syntax = Syntax(command, "bash", theme="monokai", line_numbers=False)
    panel = Panel(
        syntax,
        title=f"⚠ 需要确认（{reason}）",
        border_style="yellow",
        padding=(0, 1),
    )

    # 输出到 stdout（正常流）
    console.print()
    console.print(panel)

    # 提示用户操作
    sys.stdout.write("\n  \033[90m按 Enter 确认执行，按其他键取消\033[0m")
    sys.stdout.flush()

    # 从 /dev/tty 读取按键
    try:
        key = _read_tty_key()
    except OSError:
        # 无法读取 tty，默认拒绝
        sys.stdout.write("\n  \033[31m[无法读取输入，已取消]\033[0m\n")
        sys.stdout.flush()
        return False

    # 换行
    sys.stdout.write("\n")
    sys.stdout.flush()

    if key in ("\r", "\n"):
        sys.stdout.write("  \033[32m✓ 已确认\033[0m\n")
        sys.stdout.flush()
        return True
    else:
        sys.stdout.write("  \033[31m✗ 已取消\033[0m\n")
        sys.stdout.flush()
        return False


def build_agent(config_path: str | None = None) -> Orchestrator:
    """构建完整的 Agent 实例。

    首次运行时交互式引导用户配置 LLM。
    后续运行自动加载已有配置。
    """
    # 获取配置
    if config_path:
        config = load_config(config_path)
    else:
        config = load_config()

    # 创建 LLM Provider
    llm = create_provider({
        "provider": config.llm.provider,
        "model": config.llm.model,
        "api_key": config.llm.api_key,
        "base_url": config.llm.base_url,
    })

    # 创建工具集
    tools = build_default_tools()

    # 创建护栏
    guardrail = GuardrailEngine(
        enabled=config.guardrail.enabled,
        timeout=config.guardrail.timeout,
    )

    # 创建长期记忆
    long_term = LongTermStore(
        path=config.memory.long_term_path,
        max_entries=config.memory.max_facts,
    )

    # 创建 Orchestrator
    orchestrator = Orchestrator(
        llm=llm,
        tools=tools,
        guardrail=guardrail,
        long_term=long_term,
        max_react_steps=config.agent.max_react_steps,
        auto_confirm=config.agent.auto_confirm,
        confirm_callback=cli_confirm_callback,
    )

    logger.info(
        f"Agent 初始化完成 | LLM: {config.llm.provider}/{config.llm.model} | "
        f"Tools: {len(tools.list_tools())} | Guardrail: {'ON' if config.guardrail.enabled else 'OFF'}"
    )
    return orchestrator


async def start_agent() -> None:
    """iTerm2 Python API 入口。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    # 构建 Agent（首次运行会触发交互式配置）
    agent = build_agent()

    # 尝试导入 iterm2（仅在 iTerm2 环境中可用）
    try:
        import iterm2
    except ImportError:
        logger.warning("iterm2 模块不可用，进入 CLI 模式")
        await _cli_mode(agent)
        return

    # iTerm2 模式
    app = await iterm2.Connection.GetAsync()
    session = app.current_terminal.session

    logger.info("iTerm2 Agent 已启动")
    await session.write("\n\033[32m[Agent Ready]\033[0m 输入 /ai <自然语言> 启动智能助手\n")

    await asyncio.Event().wait()


async def _cli_mode(agent: Orchestrator) -> None:
    """CLI 交互模式。"""
    print("\033[32m=== iTerm Agent ===\033[0m")
    print("输入自然语言指令或 shell 命令")
    print("  直接输入命令 → 自动路由（中文/自然语言走 Agent，命令直接执行）")
    print("  /ai <指令>   → 强制走 Agent")
    print("  /help        → 查看帮助")
    print("  /quit        → 退出\n")

    while True:
        try:
            user_input = input("\033[36m> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q", "/quit"):
            agent.session_end()
            print("\033[90m已退出，记忆已保存。\033[0m")
            break

        # 内置命令
        if user_input == "/help":
            print("""
可用操作:
  直接输入 shell 命令（如 ls -la）→ 直接执行
  输入自然语言（如 帮我查看磁盘空间）→ Agent 处理
  /ai <指令> → 强制走 Agent
  /quit → 退出
""")
            continue

        print("\033[90m  处理中...\033[0m")
        result = await agent.handle(user_input)
        print(f"\n\033[32m{result}\033[0m\n")


if __name__ == "__main__":
    asyncio.run(start_agent())

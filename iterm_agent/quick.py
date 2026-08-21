"""快速调用入口：接收一条自然语言，调用 Agent 处理，流式输出结果后退出。

被 zsh 钩子调用，设计为单次执行、快速返回。
支持会话持久化（基于 ITERM_SESSION_ID）和记忆引擎。
支持 Markdown 渲染：流式输出完成后，如果包含 Markdown 标记，清除原始文本后用 rich 渲染。

用法：
    python3 -m iterm_agent.quick "帮我安装 Python"
    python3 -m iterm_agent.quick --json "帮我安装 Python"
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import os

# ===== 日志配置 =====
_LOG_DIR = os.path.expanduser("~/.iterm_agent")
_LOG_FILE = os.path.join(_LOG_DIR, "agent.log")
os.makedirs(_LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("quick")

# 转圈动画帧
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.1  # 每帧间隔（秒）

# Markdown 特征检测
_MD_PATTERNS = [
    re.compile(r"^#{1,6}\s", re.MULTILINE),       # 标题
    re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE),  # 无序列表
    re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE),  # 有序列表
    re.compile(r"```"),                            # 代码块
    re.compile(r"\*\*[^*]+\*\*"),                  # 加粗
    re.compile(r"`[^`]+`"),                        # 行内代码
    re.compile(r"^\s*>\s", re.MULTILINE),          # 引用
    re.compile(r"\|.*\|.*\|"),                     # 表格
]


def _has_markdown(text: str) -> bool:
    """检测文本是否包含 Markdown 标记。"""
    if not text or len(text) < 20:
        return False
    for pattern in _MD_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _render_markdown(text: str) -> None:
    """用 rich 渲染 Markdown 到终端。"""
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    console.print(Markdown(text))


async def _spinner_task(stop_event: asyncio.Event):
    """后台转圈动画任务。"""
    i = 0
    while not stop_event.is_set():
        frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        sys.stdout.write(f"\r\033[90m  {frame} 思考中...\033[0m")
        sys.stdout.flush()
        i += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SPINNER_INTERVAL)
        except asyncio.TimeoutError:
            pass
    # 停止时清除动画行
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


def main() -> None:
    args = sys.argv[1:]
    json_output = False
    force_agent = False
    if "--json" in args:
        json_output = True
        args.remove("--json")
    if "--agent" in args:
        force_agent = True
        args.remove("--agent")

    if not args:
        print("用法: python3 -m iterm_agent.quick [选项] <自然语言指令>")
        print("选项: --json  以 JSON 格式输出")
        print("       --agent  强制走 Agent（跳过路由）")
        sys.exit(1)

    user_input = " ".join(args)
    logger.info(f"Input: {user_input} (force_agent={force_agent})")

    from iterm_agent.entry import build_agent
    agent = build_agent()

    if json_output:
        result = asyncio.run(_handle_with_session(agent, user_input))
        print(json.dumps({"result": result}, ensure_ascii=False))
    else:
        asyncio.run(_stream_handle(agent, user_input, force_agent=force_agent))


async def _stream_handle(agent, user_input: str, force_agent: bool = False) -> None:
    """流式处理：先判断路由，agent 路径显示 spinner + 流式输出 + Markdown 渲染。"""
    from iterm_agent.core.router import InputRouter

    if force_agent:
        route_target = "agent"
        logger.info("Route: agent (forced by zsh plugin)")
    else:
        router = InputRouter()
        route = router.route(user_input)
        route_target = route.target
        logger.info(f"Route: {route.target} ({route.reason})")

    if route_target == "shell":
        # shell 命令：不显示 spinner，直接执行
        result = await _handle_with_session(agent, user_input)
        sys.stdout.write(result)
        sys.stdout.flush()
        if not result.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
        return

    # agent 路径：显示 spinner，流式输出
    sys.stdout.write("\n")
    sys.stdout.flush()

    stop_event = asyncio.Event()
    spinner = asyncio.create_task(_spinner_task(stop_event))

    first_token_received = False
    full_text = []  # 累积完整文本

    def on_token(token: str):
        nonlocal first_token_received
        if not first_token_received:
            stop_event.set()
            first_token_received = True
        sys.stdout.write(token)
        sys.stdout.flush()
        full_text.append(token)

    result = await _handle_with_session(agent, user_input, on_token=on_token)

    # 如果 on_token 没触发（异常降级），停止 spinner
    if not first_token_received:
        stop_event.set()

    # 等待动画任务结束
    await spinner

    # 如果 on_token 没触发，输出完整结果
    if not first_token_received:
        sys.stdout.write(result)
        sys.stdout.flush()
        sys.stdout.write("\n")
        sys.stdout.flush()
        return

    # 流式输出已完成，检查是否需要 Markdown 渲染
    accumulated = "".join(full_text)
    if _has_markdown(accumulated):
        # 计算输出行数（从 spinner 清除后的位置开始）
        line_count = accumulated.count("\n") + 1
        # 上移到输出起始位置，清除到屏幕底部
        sys.stdout.write(f"\033[{line_count}A\033[J")
        sys.stdout.flush()
        # 用 rich 渲染
        _render_markdown(accumulated)
    else:
        sys.stdout.write("\n")
        sys.stdout.flush()


async def _handle_with_session(agent, user_input: str, on_token=None) -> str:
    """带会话管理的完整处理流程。"""
    from iterm_agent.session import SessionStore
    from iterm_agent.memory.compressor import should_compress, split_for_compress, compress_messages

    # 1. 加载会话
    store = SessionStore()
    session = store.load()

    # 2. 注入上下文到 Agent
    ctx = agent.ctx
    ctx.session_id = session.session_id
    ctx.summary = session.summary
    ctx.messages = list(session.messages)

    # 3. 检索长期记忆
    relevant = agent.long_term.retrieve(user_input, top_k=3)
    ctx.long_term_memories = [e.content for e in relevant]

    # 4. 执行 Agent
    result = await agent.handle(user_input, on_token=on_token, skip_planner=True)

    # 5. 保存会话
    session.add_exchange(user_input, result)
    store.save(session)

    # 6. 检查是否需要压缩
    if should_compress(session.messages):
        old_msgs, recent_msgs = split_for_compress(session.messages)
        if old_msgs:
            new_summary = await compress_messages(
                agent.llm,
                old_msgs,
                existing_summary=session.summary,
            )
            session.summary = new_summary
            session.messages = recent_msgs
            store.save(session)

    logger.info(f"Result: {result[:100]}")
    return result


if __name__ == "__main__":
    main()

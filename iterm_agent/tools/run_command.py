"""run_command 工具：在终端执行 shell 命令。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

from iterm_agent.tools.registry import Tool

logger = logging.getLogger(__name__)

# 审计日志路径
_AUDIT_DIR = os.path.expanduser("~/.iterm_agent")
_AUDIT_FILE = os.path.join(_AUDIT_DIR, "audit.log")


def _decode_output(data: bytes) -> str:
    """解码命令输出：优先 UTF-8，失败则尝试 GBK（Windows 中文环境）。"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gbk")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")


def _audit_log(command: str, result: str, exit_code: int | None = None) -> None:
    """记录命令执行到审计日志。"""
    try:
        os.makedirs(_AUDIT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 只记录结果前 200 字符
        result_brief = result[:200].replace("\n", " ")
        with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] CMD: {command}\n")
            f.write(f"  RESULT: {result_brief}\n")
            if exit_code is not None:
                f.write(f"  EXIT: {exit_code}\n")
            f.write("\n")
    except OSError:
        pass


async def _run_command_handler(command: str, timeout: int = 30, cwd: str | None = None) -> str:
    """执行 shell 命令并返回 stdout + stderr。"""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or os.getcwd(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            result = f"[TIMEOUT] 命令执行超时（{timeout}s）: {command}"
            _audit_log(command, result, exit_code=-1)
            return result
        # Python 3.9: Process.returncode 直接调用
        # self._transport.get_returncode()，无 None 保护；
        # communicate() 后 transport 可能已被内部清理。
        try:
            returncode = proc.returncode
        except (AttributeError, TypeError):
            returncode = None

        output_parts = []
        if stdout:
            output_parts.append(_decode_output(stdout))
        if stderr:
            output_parts.append(f"[STDERR]\n{_decode_output(stderr)}")
        if not stdout and not stderr:
            output_parts.append("(no output)")
        output_parts.append(f"[EXIT CODE: {returncode}]")
        result = "\n".join(output_parts)

        # 审计日志
        _audit_log(command, result, exit_code=returncode)

        return result

    except Exception as e:
        result = f"[ERROR] 命令执行失败: {type(e).__name__}: {e}"
        _audit_log(command, result, exit_code=-1)
        return result


run_command_tool = Tool(
    name="run_command",
    description="在终端执行 shell 命令并返回输出（stdout + stderr + 退出码）",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 30",
                "default": 30,
            },
            "cwd": {
                "type": "string",
                "description": "工作目录（可选）",
            },
        },
        "required": ["command"],
    },
    handler=_run_command_handler,
)

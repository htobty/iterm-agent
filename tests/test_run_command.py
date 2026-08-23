"""测试 run_command 工具的辅助函数。"""

import pytest
from iterm_agent.tools.run_command import _decode_output


class TestDecodeOutput:
    """测试命令输出解码逻辑。"""

    def test_utf8_decode(self):
        data = "Hello, 世界".encode("utf-8")
        assert _decode_output(data) == "Hello, 世界"

    def test_gbk_decode(self):
        # Windows 中文输出（GBK 编码）
        data = "成功: 已终止进程".encode("gbk")
        result = _decode_output(data)
        assert "成功" in result
        assert "终止进程" in result

    def test_pure_ascii(self):
        data = b"OK\n"
        assert _decode_output(data) == "OK\n"

    def test_empty_bytes(self):
        assert _decode_output(b"") == ""

    def test_invalid_bytes_fallback(self):
        # 既不是合法 UTF-8 也不是合法 GBK 的字节
        data = bytes([0xFE, 0xFF, 0x00, 0x01])
        result = _decode_output(data)
        assert isinstance(result, str)  # 不抛异常即可


class TestRunCommandHandler:
    """测试 run_command 异步执行。"""

    @pytest.mark.asyncio
    async def test_simple_command(self):
        from iterm_agent.tools.run_command import _run_command_handler
        result = await _run_command_handler("echo hello")
        assert "hello" in result
        assert "[EXIT CODE: 0]" in result

    @pytest.mark.asyncio
    async def test_command_with_stderr(self):
        from iterm_agent.tools.run_command import _run_command_handler
        result = await _run_command_handler("echo err >&2")
        assert "[STDERR]" in result
        assert "err" in result

    @pytest.mark.asyncio
    async def test_command_no_output(self):
        from iterm_agent.tools.run_command import _run_command_handler
        result = await _run_command_handler("true")
        assert "(no output)" in result
        assert "[EXIT CODE: 0]" in result

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        from iterm_agent.tools.run_command import _run_command_handler
        result = await _run_command_handler("sleep 10", timeout=1)
        assert "[TIMEOUT]" in result

    @pytest.mark.asyncio
    async def test_command_nonzero_exit(self):
        from iterm_agent.tools.run_command import _run_command_handler
        result = await _run_command_handler("exit 42")
        assert "[EXIT CODE: 42]" in result

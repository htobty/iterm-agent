"""测试工具注册表。"""

import pytest
from iterm_agent.tools.registry import Tool, ToolRegistry


def _make_tool(name: str = "test_tool") -> Tool:
    async def handler(**kwargs):
        return "ok"

    return Tool(
        name=name,
        description="A test tool",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
    )


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _make_tool("my_tool")
        reg.register(tool)
        assert reg.get("my_tool") is tool
        assert reg.get("nonexistent") is None

    def test_list_tools(self):
        reg = ToolRegistry()
        reg.register(_make_tool("a"))
        reg.register(_make_tool("b"))
        names = [t.name for t in reg.list_tools()]
        assert names == ["a", "b"]

    def test_get_schemas(self):
        reg = ToolRegistry()
        reg.register(_make_tool("x"))
        schemas = reg.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "x"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        reg = ToolRegistry()
        reg.register(_make_tool("run"))
        result = await reg.execute("run", {})
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        result = await reg.execute("nope", {})
        assert "[ERROR]" in result

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        async def bad_handler(**kwargs):
            raise ValueError("boom")

        tool = Tool(
            name="bad",
            description="bad tool",
            parameters={"type": "object", "properties": {}},
            handler=bad_handler,
        )
        reg = ToolRegistry()
        reg.register(tool)
        result = await reg.execute("bad", {})
        assert "[ERROR]" in result
        assert "boom" in result


class TestBuildDefaultTools:
    def test_build_without_long_term(self):
        from iterm_agent.tools.registry import build_default_tools
        reg = build_default_tools(long_term=None)
        names = [t.name for t in reg.list_tools()]
        assert "run_command" in names
        assert "remember" not in names

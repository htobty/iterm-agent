"""InputRouter 单元测试。

覆盖：
- Bug 修复：路径命令不被误判为自然语言
- Bug 修复：中文问句不被误判为命令
- 回归：常规命令和自然语言路由正确
"""

import pytest

from iterm_agent.core.router import InputRouter


@pytest.fixture
def router():
    return InputRouter()


class TestPathCommands:
    """首词含路径 → 一定是 shell 命令。"""

    @pytest.mark.parametrize("text", [
        "~/miniconda3/envs/qwen3tts/bin/python qwen3_tts_server_mlx.py",
        "/usr/bin/python3 script.py",
        "./run.sh",
        "../tools/build.sh --release",
        "~/bin/node server.js",
        "/opt/homebrew/bin/ffmpeg -i input.mp4 output.mp3",
    ])
    def test_path_commands_are_shell(self, router, text):
        result = router.route(text)
        assert result.target == "shell", f"路径命令被误判: {text}"


class TestChineseNL:
    """中文自然语言 → 一定是 agent。"""

    @pytest.mark.parametrize("text", [
        "Prompt 缓存命中率是多少啊",
        "帮我安装 Python",
        "怎么查看磁盘空间",
        "如何配置 nginx 反向代理？",
        "192.168.50.223 就是我的台式机",
        "这个报错是什么意思",
        "能不能帮我看看这段代码",
        "有没有更好的方案",
    ])
    def test_chinese_nl_is_agent(self, router, text):
        result = router.route(text)
        assert result.target == "agent", f"中文问句被误判为命令: {text}"


class TestKnownCommands:
    """已知命令白名单 → shell。"""

    @pytest.mark.parametrize("text", [
        "ls -la",
        "cd /tmp",
        "git status",
        "python3 -m http.server 8000",
        "docker ps",
        "grep -r 'TODO' .",
        "npm install",
        "make build",
    ])
    def test_known_commands_are_shell(self, router, text):
        result = router.route(text)
        assert result.target == "shell", f"已知命令被误判: {text}"


class TestAgentPrefix:
    """ai 前缀 → 强制 agent。"""

    @pytest.mark.parametrize("text,expected_cleaned", [
        ("ai 帮我写个脚本", "帮我写个脚本"),
        ("ai 解释一下这个错误", "解释一下这个错误"),
    ])
    def test_ai_prefix(self, router, text, expected_cleaned):
        result = router.route(text)
        assert result.target == "agent"
        assert result.cleaned_input == expected_cleaned


class TestEdgeCases:
    """边界情况。"""

    def test_empty_input(self, router):
        result = router.route("")
        assert result.target == "shell"

    def test_whitespace_only(self, router):
        result = router.route("   ")
        assert result.target == "shell"

    def test_unknown_ascii_word_defaults_to_shell(self, router):
        """未知纯 ASCII 单词默认走 shell（不拦截）。"""
        result = router.route("foobar --help")
        assert result.target == "shell"

    def test_known_command_with_chinese_args_is_agent(self, router):
        """已知命令 + 中文参数（高占比）→ agent（用户在描述意图）。"""
        # "git 提交代码" 中文占比 50% > 30%，走 agent 帮用户生成正确命令
        result = router.route("git 提交代码")
        assert result.target == "agent"

    def test_known_command_with_ascii_args_is_shell(self, router):
        """已知命令 + 纯 ASCII 参数 → shell。"""
        result = router.route("git commit -m 'fix bug'")
        assert result.target == "shell"

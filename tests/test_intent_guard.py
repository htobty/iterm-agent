"""测试意图校验模块。"""

import pytest
from iterm_agent.guardrail.intent_guard import IntentGuard


@pytest.fixture
def guard():
    return IntentGuard()


class TestIntentGuard:
    """测试 IntentGuard.check()。"""

    def test_safe_command_passes(self, guard):
        passed, reason = guard.check("帮我看看目录", "ls -la")
        assert passed is True
        assert reason == ""

    def test_rm_with_intent_passes(self, guard):
        passed, reason = guard.check("帮我删除 build 目录", "rm -rf ./build")
        assert passed is True

    def test_rm_without_intent_blocked(self, guard):
        passed, reason = guard.check("帮我看看目录", "rm -rf ./build")
        assert passed is False
        assert "危险操作" in reason

    def test_sudo_with_intent_passes(self, guard):
        passed, reason = guard.check("用管理员权限安装", "sudo apt install nginx")
        assert passed is True

    def test_sudo_without_intent_blocked(self, guard):
        passed, reason = guard.check("帮我安装 nginx", "sudo apt install nginx")
        assert passed is False

    def test_git_push_with_intent_passes(self, guard):
        passed, reason = guard.check("帮我推送到远程", "git push origin main")
        assert passed is True

    def test_git_push_without_intent_blocked(self, guard):
        passed, reason = guard.check("帮我看看状态", "git push origin main")
        assert passed is False

    def test_kill_with_intent_passes(self, guard):
        passed, reason = guard.check("帮我杀掉那个进程", "kill -9 1234")
        assert passed is True

    def test_kill_without_intent_blocked(self, guard):
        passed, reason = guard.check("帮我看看进程", "kill -9 1234")
        assert passed is False

    def test_multi_command_all_safe(self, guard):
        passed, reason = guard.check("帮我看看", "ls -la && pwd")
        assert passed is True

    def test_multi_command_one_dangerous(self, guard):
        passed, reason = guard.check("帮我看看", "ls -la && rm -rf /tmp/x")
        assert passed is False

    def test_english_intent(self, guard):
        passed, reason = guard.check("please delete the build folder", "rm -rf ./build")
        assert passed is True

    def test_long_command_passes(self, guard):
        """命令长度不再限制。"""
        long_cmd = "ssh user@host " + "a" * 600
        passed, reason = guard.check("帮我远程执行", long_cmd)
        assert passed is True

"""测试配置加载模块。"""

import pytest
from iterm_agent.config import AppConfig, load_config


class TestAppConfigFromDict:
    """测试 AppConfig.from_dict 解析。"""

    def test_defaults(self):
        cfg = AppConfig.from_dict({})
        assert cfg.llm.provider == "openai"
        assert cfg.llm.model == "gpt-4o"
        assert cfg.llm.api_key is None
        assert cfg.llm.base_url is None
        assert cfg.llm.temperature == 0.2
        assert cfg.llm.max_tokens == 4096
        assert cfg.agent.max_react_steps == 3
        assert cfg.guardrail.enabled is True
        assert cfg.guardrail.timeout == 30
        assert cfg.memory.max_facts == 50

    def test_full_config(self):
        data = {
            "llm": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "api_key": "sk-ant-test",
                "base_url": "https://api.anthropic.com",
                "temperature": 0.5,
                "max_tokens": 8192,
            },
            "agent": {
                "max_react_steps": 20,
                "auto_confirm": True,
            },
            "guardrail": {
                "enabled": False,
                "timeout": 60,
            },
            "memory": {
                "long_term_path": "/tmp/mem.json",
                "max_facts": 100,
            },
        }
        cfg = AppConfig.from_dict(data)
        assert cfg.llm.provider == "anthropic"
        assert cfg.llm.model == "claude-sonnet-4-20250514"
        assert cfg.llm.api_key == "sk-ant-test"
        assert cfg.llm.temperature == 0.5
        assert cfg.llm.max_tokens == 8192
        assert cfg.agent.max_react_steps == 20
        assert cfg.agent.auto_confirm is True
        assert cfg.guardrail.enabled is False
        assert cfg.guardrail.timeout == 60
        assert cfg.memory.long_term_path == "/tmp/mem.json"
        assert cfg.memory.max_facts == 100

    def test_partial_config(self):
        data = {"llm": {"model": "deepseek-chat"}}
        cfg = AppConfig.from_dict(data)
        assert cfg.llm.model == "deepseek-chat"
        assert cfg.llm.provider == "openai"  # 默认值保留
        assert cfg.guardrail.enabled is True


class TestLoadConfig:
    """测试 load_config 文件加载。"""

    def test_load_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "llm:\n  model: test-model\n  api_key: test-key\n",
            encoding="utf-8",
        )
        cfg = load_config(config_file)
        assert cfg.llm.model == "test-model"
        assert cfg.llm.api_key == "test-key"

    def test_load_nonexistent_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.llm.model == "gpt-4o"

    def test_load_empty_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        cfg = load_config(config_file)
        assert cfg.llm.provider == "openai"

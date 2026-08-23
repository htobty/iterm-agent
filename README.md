---
name: iterm_agent_readme
title: iTerm Agent
description: English | 中文 在 iTerm2 里输入自然语言，LLM 自己规划、自己执行、自己验证。普通命令不受影响，装完就忘。
summary: English | 中文 在 iTerm2 里输入自然语言，LLM 自己规划、自己执行、自己验证。普通命令不受影响，装完就忘。
keywords: []
category: Users/htob/code/iterm-agent
---

# iTerm Agent

**A lightweight agent that turns iTerm2 into your intelligent assistant.**

[中文](README.zh.md) | English

Type natural language in iTerm2. The agent plans, executes, and verifies — all by itself. Your normal commands are untouched. Install and forget.

```
➜  ~ 帮我看看当前目录有哪些 Python 项目
当前目录下有 3 个 Python 项目：
  1. iterm-agent/ — 本项目
  2. data-pipeline/ — ETL 脚本
  3. web-scraper/ — 爬虫工具

➜  ~ 帮我启动 192.168.50.223 上的模型服务
[执行] ssh htob@192.168.50.223 "start llama-server.exe --port 8989 ..."
[执行] ssh htob@192.168.50.223 "curl -s http://localhost:8989/health"
模型服务已启动，健康检查通过。

➜  ~ ls -la          ← normal command, not intercepted
total 48
drwxr-xr-x  12 htob  staff  384 Aug 21 10:00 .
```

## The Problem

Every day in the terminal: SSH in → `cd` → `git pull` → run tests → check logs → restart service. Switch machines, do it again. Forget a flag, `--help`. Typo a command, start over.

iterm-agent lets you say it in one sentence. It's not autocomplete. It's not a translator. It's an agent that plans multi-step operations on its own.

## How It Differs from Codex / Claude Code

| | Codex / Claude Code | iterm-agent |
|---|---|---|
| Focus | Software engineering (write code, refactor) | Terminal operations (ops, remote management, daily chores) |
| Model | Locked to vendor | Any OpenAI-compatible endpoint, including local models |
| Cost | Per-token billing | Free with local models |
| Privacy | Context sent to cloud | Can stay entirely on your machine |
| Environment | Sandbox / project directory | Your real shell, can SSH anywhere |
| Intrusiveness | Separate tool | Embedded in your existing terminal, invisible when not used |

Write code with Claude Code. Get things done with iterm-agent. Complementary, not competing.

## Key Features

### Smart Routing — Never Hijacks Your Shell

Type `git status` and it runs `git status`. Type `ssh htob@192.168.50.223 "H:\\下载\\llama-server.exe"` and it runs normally — even with Chinese characters in the path.

Routing is based on **structural signals** (`-`, `@`, `/`, `~`, `=`, `:`, quotes, file extensions), not language enumeration. Works with Chinese, Japanese, Korean, or any language.

### Any Model, Zero Lock-in

DeepSeek, Moonshot, OpenAI, local Ollama, llama.cpp, vLLM — change one line:

```yaml
llm:
  base_url: "http://localhost:8080/v1"   # local llama.cpp
  model: "qwen3-32b"
  api_key: "not-needed"
```

### Long-term Memory

Tell it once: "My desktop is 192.168.50.223, username htob." It saves to a local JSON file. Every future remote operation uses it automatically. No repetition.

### A Real Agent

ReAct loop, up to 20 steps. It will:
- `ls` to see the directory structure
- `cd` into it
- Execute the operation
- Verify the result
- Retry with a different approach if it fails

Not one-shot Q&A. Autonomous planning + execution + verification.

### Security Guardrails

It actually runs commands, so:

- **Blacklist**: `rm -rf /`, `mkfs`, `dd of=/dev/` — rejected outright
- **Danger confirmation**: `rm -rf ./subdir`, `chmod 777`, `curl | sh` — requires Enter to confirm
- **Timeout**: commands auto-killed after timeout
- **Intent check**: verifies LLM-generated commands match your original intent
- **Audit log**: every command and result written to `~/.iterm_agent/audit.log`

### Streaming Output + Markdown Rendering

LLM responses stream in real-time. After completion, tables, code blocks, and headings are rendered with rich.

## Install

```bash
git clone https://github.com/htobty/iterm-agent.git && bash iterm-agent/install.sh
```

Reopen iTerm2. Done.

### Requirements

- macOS + iTerm2
- Python ≥ 3.9
- Any OpenAI-compatible LLM (local or cloud)

### Configuration

Config file: `~/.iterm_agent/config.yaml`

```yaml
llm:
  provider: openai
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-xxx"
  model: "deepseek-chat"

agent:
  max_react_steps: 20

guardrail:
  enabled: true
  timeout: 30
```

| Field | Description |
|-------|-------------|
| `llm.base_url` | Any OpenAI-compatible endpoint |
| `llm.model` | Model name |
| `llm.api_key` | Supports `${ENV_VAR}` references |
| `agent.max_react_steps` | Max tool calls per turn (default 20) |
| `guardrail.enabled` | Security guardrail toggle |
| `guardrail.timeout` | Command timeout in seconds |

## Usage

```bash
# Natural language → Agent handles it
帮我安装 Python
看看 nginx 日志今天有没有 500
把桌面上的 report.csv 里销售额大于 10 万的行筛出来

# Remote operations
帮我关闭 192.168.50.223 上的模型服务
SSH 到台式机看看磁盘还剩多少

# Memory
192.168.50.223 就是我的台式机，请记住

# Force agent mode with 'ai' prefix
ai what is docker

# Normal commands → not intercepted
ls -la
git status
docker ps
```

### Temporarily Disable

```bash
export ITERM_AGENT_ENABLED=0
```

## How It Works

```
User input
    │
    ▼
┌──────────────────────────────────────┐
│  zsh plugin (iterm-agent.zsh)        │
│  Structural signal detection → route │
└────────────┬─────────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
  Shell command    Natural language
  (run directly)   (invoke Agent)
                     │
                     ▼
              ┌─────────────┐
              │  Executor    │  ← ReAct loop (max 20 steps)
              │  (LLM+Tools) │
              └──────┬──────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
         run_command    remember
         (guardrails)   (long-term memory)
```

### Routing Rules

| Condition | Route |
|-----------|-------|
| Contains shell syntax (`\|` `>` `<` `&&` `\|\|` `;`) | Shell |
| First word is not a known command | Agent |
| First word is a command, args are pure ASCII | Shell |
| First word is a command, args have non-ASCII + structural signals | Shell |
| First word is a command, args have non-ASCII + no structural signals | Agent |
| `ai` prefix | Agent (forced) |

Structural signals: `-`, `--`, `@`, `/`, `\`, `~`, `=`, `:`, quotes, file extensions. Language-agnostic by design.

## Project Structure

```
iterm-agent/
├── iterm-agent.zsh            # zsh plugin (entry + routing)
├── install.sh                 # One-line installer
├── pyproject.toml
└── iterm_agent/
    ├── quick.py               # CLI entry (called by zsh plugin)
    ├── entry.py               # Agent factory
    ├── config.py              # Config loading
    ├── session.py             # Session persistence (file locks)
    ├── core/
    │   ├── orchestrator.py    # Dispatcher
    │   ├── executor.py        # ReAct executor
    │   └── context.py         # Context builder
    ├── llm/
    │   ├── base.py            # LLM abstract interface
    │   ├── openai_provider.py # OpenAI-compatible (streaming + retry)
    │   └── factory.py         # Provider factory
    ├── guardrail/
    │   ├── engine.py          # Security guardrails (blacklist + confirm)
    │   └── intent_guard.py    # Intent verification
    ├── memory/
    │   ├── long_term.py       # Long-term memory (JSON)
    │   └── compressor.py      # Context compression
    └── tools/
        ├── registry.py        # Tool registry
        ├── run_command.py     # Command execution (timeout + encoding)
        └── remember.py        # Memory write
```

## Logs

| File | Content |
|------|---------|
| `~/.iterm_agent/agent.log` | Runtime log (routing, LLM calls, tool execution) |
| `~/.iterm_agent/audit.log` | Command audit (every command + result) |

## Development

```bash
cd iterm-agent
PYTHONPATH=. python3 -m iterm_agent.quick "test"
```

## License

MIT

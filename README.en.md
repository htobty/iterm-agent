

# iTerm Agent

[English](README.en.md) | [中文](README.md)

Type natural language directly in your iTerm2 terminal and let an LLM handle it. No window switching, no REPL — just type and go, with streaming output.

```
➜  ~ show me all Python projects in this directory
  ⠋ Thinking...
Found 3 Python projects in the current directory:
  1. iterm-agent/ — this project
  2. data-pipeline/ — ETL scripts
  3. web-scraper/ — scraping tools

➜  ~ install requests
  ⠋ Thinking...
[Running] pip3 install requests
[OK] Successfully installed requests-2.31.0

➜  ~ ls -la
total 48
drwxr-xr-x  12 htob  staff  384 Aug 21 10:00 .
...
```

## Features

- **Zero context switching** — type natural language in your existing shell; regular commands work as usual, no prefix or mode toggle needed
- **Streaming output** — tokens render as they arrive; a spinner shows while waiting for the first token
- **Any OpenAI-compatible endpoint** — point `base_url` at OpenAI, Moonshot, DeepSeek, vLLM, or anything else that speaks the OpenAI API
- **Session management** — each iTerm2 window gets its own persistent session; long contexts are compressed by the LLM automatically
- **Long-term memory** — opt-in (you must explicitly ask to remember something), retrieved across sessions
- **Safety guardrails** — command blacklist, confirmation for dangerous operations, timeout enforcement, intent validation
- **Markdown rendering** — after streaming completes, output is auto-detected and rendered with rich (tables, code blocks, etc.)

## How It Works

```
User input
    │
    ▼
┌─────────────────────────────────┐
│  zsh plugin (iterm-agent.zsh)   │
│  intercepts accept-line,        │
│  decides routing                │
└────────────┬────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
  shell command    natural language
  (executed as-is) (sent to Agent)
                     │
                     ▼
              ┌─────────────┐
              │ Orchestrator │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │   Executor   │  ← ReAct loop
              │ (LLM + tools)│     up to N steps
              └──────┬──────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
         run_command    direct reply
         (guardrails)   (streamed)
```

The zsh plugin routes input based on these rules:

| Condition | Route |
|-----------|-------|
| First character is non-ASCII (CJK, etc.) | Agent |
| Starts with `ai ` | Agent (forced) |
| Contains shell syntax (`|`, `>`, `&&`, etc.) | Shell |
| First word is a known command/builtin/function/alias | Shell |
| Anything else | Agent |

## Installation

### Prerequisites

- macOS (iTerm2)
- Python ≥ 3.10
- An API key for any OpenAI-compatible LLM endpoint

### Steps

```bash
git clone https://github.com/htobty/iterm-agent.git ~/code/iterm-agent && bash ~/code/iterm-agent/install.sh
```

The installer will prompt for your LLM config (base_url, model, api_key) and handle everything else.
Open a new iTerm2 window after installation to start using it.

> If `~/.iterm_agent/config.yaml` already exists, the installer skips config and just ensures deps and zshrc are in place (idempotent, safe to re-run).

### Configuration

Config file lives at `~/.iterm_agent/config.yaml`:

| Field | Description |
|-------|-------------|
| `llm.provider` | Always `openai` (OpenAI-compatible protocol) |
| `llm.model` | Model name, e.g. `gpt-4o`, `kimi-k2`, `deepseek-chat` |
| `llm.api_key` | API key; supports `${ENV_VAR}` references |
| `llm.base_url` | Custom endpoint, e.g. `https://api.moonshot.cn/v1` |
| `llm.temperature` | Sampling temperature (auto-overridden to 1 for reasoning models) |
| `llm.max_tokens` | Max output tokens |
| `agent.max_react_steps` | Max tool-call rounds per query |
| `agent.auto_confirm` | Skip confirmation for dangerous commands (not recommended) |
| `guardrail.enabled` | Enable safety guardrails |
| `guardrail.timeout` | Command timeout in seconds |
| `memory.long_term_path` | Path for long-term memory store |
| `memory.max_facts` | Max entries in long-term memory |

### Using Different LLMs

```yaml
# Moonshot Kimi
llm:
  provider: openai
  model: kimi-k2
  api_key: sk-xxx
  base_url: https://api.moonshot.cn/v1

# DeepSeek
llm:
  provider: openai
  model: deepseek-chat
  api_key: sk-xxx
  base_url: https://api.deepseek.com/v1

# Local vLLM
llm:
  provider: openai
  model: qwen2.5-72b
  api_key: not-needed
  base_url: http://localhost:8000/v1
```

## Usage

After installation, just type in iTerm2:

```bash
# Natural language → Agent handles it
➜  ~ install Python
➜  ~ check git status in this directory
➜  ~ write a Python script that reads a CSV and counts rows

# ai prefix → force Agent mode (even if it looks like a command)
➜  ~ ai ls -la

# Regular commands → executed normally
➜  ~ ls -la
➜  ~ git status
```

### Temporarily Disable

```bash
export ITERM_AGENT_ENABLED=0
```

### Logs

| File | Contents |
|------|----------|
| `~/.iterm_agent/agent.log` | Agent runtime log (routing, LLM calls, tool execution) |
| `~/.iterm_agent/audit.log` | Command audit log (every executed command and its result) |

## Safety

Every command the Agent wants to run passes through multiple checks:

1. **Blacklist** — instant rejection, no override (e.g. `rm -rf /`, `mkfs`, `dd of=/dev/`)
2. **Danger patterns** — requires user to press Enter to confirm (e.g. `rm -rf ./subdir`, `chmod 777`, `curl | sh`)
3. **Timeout** — commands exceeding `guardrail.timeout` seconds are killed
4. **Intent validation** — checks whether the generated command matches the user's original intent; mismatches are blocked

Confirmation I/O goes through `/dev/tty` directly, independent of stdin.

## Project Structure

```
iterm-agent/
├── iterm-agent.zsh            # zsh plugin (entry point)
├── pyproject.toml
├── README.md
├── README.en.md
└── iterm_agent/
    ├── __init__.py
    ├── quick.py               # Quick invocation entry (called by zsh plugin)
    ├── entry.py               # Agent builder
    ├── config.py              # Config loading
    ├── session.py             # Session persistence
    ├── core/
    │   ├── orchestrator.py    # Orchestrator
    │   ├── executor.py        # ReAct executor
    │   ├── router.py          # Input router (shell vs agent)
    │   └── context.py         # Agent context
    ├── llm/
    │   ├── base.py            # LLM abstract interface
    │   ├── openai_provider.py # OpenAI-compatible impl (with streaming)
    │   └── factory.py         # Provider factory
    ├── guardrail/
    │   ├── engine.py          # Safety guardrail engine
    │   └── intent_guard.py    # Intent validation
    ├── memory/
    │   ├── long_term.py       # Long-term memory (JSON persistence)
    │   └── compressor.py      # Context compression
    └── tools/
        ├── registry.py        # Tool registry
        └── run_command.py     # Command execution tool
```

## Development

```bash
cd ~/code/iterm-agent
PYTHONPATH=. python3 -m iterm_agent.quick "test it"
```

## License

MIT

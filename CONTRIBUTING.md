# Contributing to iTerm-Agent

Thanks for your interest! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/htobty/iterm-agent.git
cd iterm-agent
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/
```

## Project Structure

- `iterm-agent.zsh` — zsh plugin (routing logic)
- `iterm_agent/core/` — orchestrator, executor, context
- `iterm_agent/llm/` — LLM providers
- `iterm_agent/guardrail/` — security guardrails
- `iterm_agent/memory/` — long-term memory
- `iterm_agent/tools/` — tool registry

## What We Need Help With

- Windows Terminal / Linux terminal support
- More guardrail rules
- Better error messages
- Test coverage
- Documentation improvements

## Guidelines

- Keep it simple. The whole project is ~800 lines by design.
- Follow existing code style (no formatter enforced yet).
- One PR per feature/fix. Describe what it does and why.
- Test locally with `PYTHONPATH=. python3 -m iterm_agent.quick "your test"` before submitting.

## Questions?

Open an issue or start a discussion. We reply within 24 hours.

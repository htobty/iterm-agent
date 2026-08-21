# iTerm Agent

[English](README.en.md) | [中文](README.md)

在 iTerm2 终端里直接输入自然语言，由 LLM 驱动执行任务。不需要切换窗口、不需要打开 REPL，输入即执行，流式输出。

```
➜  ~ 帮我看看当前目录有哪些 Python 项目
  ⠋ 思考中...
当前目录下有 3 个 Python 项目：
  1. iterm-agent/ — 本项目
  2. data-pipeline/ — ETL 脚本
  3. web-scraper/ — 爬虫工具

➜  ~ 安装 requests 库
  ⠋ 思考中...
[执行] pip3 install requests
[OK] Successfully installed requests-2.31.0

➜  ~ ls -la
total 48
drwxr-xr-x  12 htob  staff  384 Aug 21 10:00 .
...
```

## 特性

- **零切换** — 在现有 shell 中直接输入自然语言，普通命令照常执行，无需前缀或模式切换
- **流式输出** — LLM 首字即出，逐 token 渲染，等待时显示 spinner
- **任意 OpenAI 兼容接口** — 通过 `base_url` 接入 OpenAI、Moonshot、DeepSeek、vLLM 等
- **会话管理** — 每个 iTerm2 窗口独立会话，上下文自动持久化，超长时 LLM 压缩
- **长期记忆** — 用户显式要求时写入，跨会话检索
- **安全护栏** — 命令黑名单、危险操作确认、超时控制、意图校验
- **Markdown 渲染** — 输出完成后自动检测并用 rich 渲染表格、代码块等

## 工作原理

```
用户输入
    │
    ▼
┌─────────────────────────────────┐
│  zsh 插件 (iterm-agent.zsh)     │
│  拦截 accept-line，判断路由     │
└────────────┬────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
  shell 命令      自然语言
  (直接执行)      (调用 Agent)
                     │
                     ▼
              ┌─────────────┐
              │  Orchestrator│
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │   Executor   │  ← ReAct 循环
              │  (LLM + 工具)│     最多 N 轮
              └──────┬──────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
         run_command    直接回复
         (安全护栏)     (流式输出)
```

zsh 插件通过以下规则判断输入类型：

| 条件 | 路由 |
|------|------|
| 首字符为非 ASCII（中文等） | Agent |
| 以 `ai ` 开头 | Agent（强制） |
| 包含 shell 语法（`|`、`>`、`&&` 等） | Shell |
| 首词是已知命令/内建/函数/别名 | Shell |
| 其他 | Agent |

## 安装

### 前置要求

- macOS（iTerm2）
- Python ≥ 3.10
- 一个 OpenAI 兼容的 LLM API Key

### 步骤

```bash
# 1. 克隆项目
git clone https://github.com/htobty/iterm-agent.git ~/code/iterm-agent

# 2. 运行安装脚本（自动装依赖、生成配置、配置 zshrc）
bash ~/code/iterm-agent/install.sh
```

安装脚本会交互式询问 LLM 配置（base_url、model、api_key），其余全自动。
安装完成后重开 iTerm2 窗口即可使用。

> 如果已有 `~/.iterm_agent/config.yaml`，脚本会跳过配置步骤，仅确保依赖和 zshrc 就绪（可重复执行）。

### 配置说明

配置文件位于 `~/.iterm_agent/config.yaml`：

| 字段 | 说明 |
|------|------|
| `llm.provider` | 固定为 `openai`（OpenAI 兼容接口） |
| `llm.model` | 模型名，如 `gpt-4o`、`kimi-k2`、`deepseek-chat` |
| `llm.api_key` | API Key，支持 `${ENV_VAR}` 环境变量引用 |
| `llm.base_url` | 自定义 endpoint，如 `https://api.moonshot.cn/v1` |
| `llm.temperature` | 采样温度（推理模型会自动覆盖为 1） |
| `llm.max_tokens` | 最大输出 token 数 |
| `agent.max_react_steps` | 单轮最大工具调用次数 |
| `agent.auto_confirm` | `true` 跳过危险命令确认（不推荐） |
| `guardrail.enabled` | 是否启用安全护栏 |
| `guardrail.timeout` | 命令超时秒数 |
| `memory.long_term_path` | 长期记忆存储路径 |
| `memory.max_facts` | 长期记忆最大条目数 |

### 使用不同 LLM

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

# 本地 vLLM
llm:
  provider: openai
  model: qwen2.5-72b
  api_key: not-needed
  base_url: http://localhost:8000/v1
```

## 使用

安装完成后，在 iTerm2 中直接输入：

```bash
# 自然语言 → Agent 处理
➜  ~ 帮我安装 Python
➜  ~ 查看当前目录的 git 状态
➜  ~ 写一个 Python 脚本读取 CSV 并统计行数

# ai 前缀 → 强制走 Agent（即使看起来像命令）
➜  ~ ai ls -la

# 普通命令 → 正常执行
➜  ~ ls -la
➜  ~ git status
```

### 临时禁用

```bash
export ITERM_AGENT_ENABLED=0
```

### 日志

| 文件 | 内容 |
|------|------|
| `~/.iterm_agent/agent.log` | Agent 运行日志（路由、LLM 调用、工具执行） |
| `~/.iterm_agent/audit.log` | 命令审计日志（每条执行的命令及结果） |

## 安全机制

Agent 执行命令前经过多层检查：

1. **黑名单** — 匹配即拒绝，不可执行（如 `rm -rf /`、`mkfs`、`dd of=/dev/`）
2. **危险模式** — 需要用户按 Enter 确认（如 `rm -rf ./subdir`、`chmod 777`、`curl | sh`）
3. **超时控制** — 命令超过 `guardrail.timeout` 秒自动终止
4. **意图校验** — 检查 LLM 生成的命令是否与用户原始意图匹配，不匹配则拦截

确认交互通过 `/dev/tty` 直接读写终端，不依赖 stdin。

## 项目结构

```
iterm-agent/
├── iterm-agent.zsh            # zsh 插件（入口）
├── pyproject.toml
├── README.md
└── iterm_agent/
    ├── __init__.py
    ├── quick.py               # 快速调用入口（被 zsh 插件调用）
    ├── entry.py               # Agent 构建工厂
    ├── config.py              # 配置加载
    ├── session.py             # 会话持久化
    ├── core/
    │   ├── orchestrator.py    # 调度器
    │   ├── executor.py        # ReAct 执行器
    │   ├── router.py          # 输入路由（shell vs agent）
    │   └── context.py         # Agent 上下文
    ├── llm/
    │   ├── base.py            # LLM 抽象接口
    │   ├── openai_provider.py # OpenAI 兼容实现（含流式）
    │   └── factory.py         # Provider 工厂
    ├── guardrail/
    │   ├── engine.py          # 安全护栏引擎
    │   └── intent_guard.py    # 意图校验
    ├── memory/
    │   ├── long_term.py       # 长期记忆（JSON 持久化）
    │   └── compressor.py      # 上下文压缩
    └── tools/
        ├── registry.py        # 工具注册表
        └── run_command.py     # 命令执行工具
```

## 开发

```bash
cd ~/code/iterm-agent
PYTHONPATH=. python3 -m iterm_agent.quick "测试一下"
```

## License

MIT

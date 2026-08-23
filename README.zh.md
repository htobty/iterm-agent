---
name: iterm_agent_readme_zh
title: iTerm Agent
description: 跟终端说人话，它自己把活干完。
summary: 跟终端说人话，它自己把活干完。
keywords: []
category: Users/htob/code/iterm-agent
---

# iTerm Agent

**跟终端说人话，它自己把活干完。**

中文 | [English](README.md)

在 iTerm2 里输入自然语言，Agent 自己规划、自己执行、自己验证。普通命令不受影响，装完就忘。

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

➜  ~ ls -la          ← 正常命令，不拦截
total 48
drwxr-xr-x  12 htob  staff  384 Aug 21 10:00 .
```

## 它解决什么问题

每天在终端里重复：SSH 上去 → `cd` → `git pull` → 跑测试 → 看日志 → 重启服务。换个环境再来一遍。参数记不住就 `--help`，命令拼错了就重来。

iterm-agent 让你用一句话完成这些。它不是补全，不是翻译，是一个能自主规划多步操作的 Agent。

## 和 Codex / Claude Code 的区别

| | Codex / Claude Code | iterm-agent |
|---|---|---|
| 定位 | 软件工程（写代码、重构） | 终端操作（运维、远程管理、日常杂活） |
| 模型 | 绑定厂商 | 任意 OpenAI 兼容接口，含本地模型 |
| 成本 | 按 token 付费 | 本地模型零成本 |
| 隐私 | 上下文发到云端 | 可以完全不出机器 |
| 环境 | 沙箱 / 项目目录 | 你的真实 shell，能 SSH 到任何机器 |
| 侵入性 | 独立工具 | 嵌在现有终端，不用时透明 |

写代码用 Claude Code，干活用 iterm-agent。互补，不冲突。

## 核心特点

### 智能路由，不劫持你的终端

输入 `git status` 就是 `git status`，输入 `ssh htob@192.168.50.223 "H:\\下载\\llama-server.exe"` 也正常执行——即使参数里有中文路径。

路由逻辑基于**结构信号**（`-`、`@`、`/`、`~`、`=`、`:`、引号、文件扩展名），不依赖语言枚举。中文、日文、韩文、任何语言的自然语言都能正确识别。

### 模型随便换

不绑定任何厂商。DeepSeek、Moonshot、OpenAI、本地 Ollama、llama.cpp、vLLM——改一行 `base_url`：

```yaml
llm:
  base_url: "http://localhost:8080/v1"   # 本地 llama.cpp
  model: "qwen3-32b"
  api_key: "not-needed"
```

### 长期记忆

告诉它一次"我的台式机 IP 是 192.168.50.223，用户名 htob"，它存到本地 JSON。以后所有远程操作自动带上，不用每次重复。

### 真正的 Agent

ReAct 循环，最多 20 步。它会：
- 先 `ls` 看目录结构
- 再 `cd` 进去
- 执行操作
- 验证结果
- 失败了换个方式重试

不是一问一答，是自主规划 + 执行 + 验证。

### 安全护栏

它真的会执行命令，所以：

- **黑名单**：`rm -rf /`、`mkfs`、`dd of=/dev/` 直接拒绝
- **危险确认**：`rm -rf ./subdir`、`chmod 777`、`curl | sh` 需要你按 Enter 确认
- **超时控制**：命令超时自动 kill
- **意图校验**：检查 LLM 生成的命令是否偏离你的原始意图
- **审计日志**：每条命令及结果写入 `~/.iterm_agent/audit.log`

### 流式输出 + Markdown 渲染

LLM 回复实时流式显示，结束后自动用 rich 渲染表格、代码块、标题。

## 安装

```bash
git clone https://github.com/htobty/iterm-agent.git && bash iterm-agent/install.sh
```

重开 iTerm2 窗口，完事。

### 前置要求

- macOS + iTerm2
- Python ≥ 3.9
- 一个 OpenAI 兼容的 LLM（本地或云端）

### 配置

配置文件：`~/.iterm_agent/config.yaml`

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

| 字段 | 说明 |
|------|------|
| `llm.base_url` | 任意 OpenAI 兼容 endpoint |
| `llm.model` | 模型名 |
| `llm.api_key` | 支持 `${ENV_VAR}` 环境变量引用 |
| `agent.max_react_steps` | 单轮最大工具调用次数（默认 20） |
| `guardrail.enabled` | 安全护栏开关 |
| `guardrail.timeout` | 命令超时秒数 |

## 使用

```bash
# 自然语言 → Agent 处理
帮我安装 Python
看看 nginx 日志今天有没有 500
把桌面上的 report.csv 里销售额大于 10 万的行筛出来

# 远程操作
帮我关闭 192.168.50.223 上的模型服务
SSH 到台式机看看磁盘还剩多少

# 记忆
192.168.50.223 就是我的台式机，请记住

# ai 前缀 → 强制走 Agent
ai what is docker

# 普通命令 → 不拦截
ls -la
git status
docker ps
```

### 临时禁用

```bash
export ITERM_AGENT_ENABLED=0
```

## 工作原理

```
用户输入
    │
    ▼
┌──────────────────────────────────────┐
│  zsh 插件 (iterm-agent.zsh)          │
│  结构信号检测 → 路由判断              │
└────────────┬─────────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
  shell 命令      自然语言
  (直接执行)      (调用 Agent)
                     │
                     ▼
              ┌─────────────┐
              │  Executor    │  ← ReAct 循环（最多 20 步）
              │  (LLM + 工具)│
              └──────┬──────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
         run_command    remember
         (安全护栏)     (长期记忆)
```

### 路由规则

| 条件 | 路由 |
|------|------|
| 含 shell 语法（`\|` `>` `<` `&&` `\|\|` `;`） | Shell |
| 首词不是已知命令 | Agent |
| 首词是命令，参数纯 ASCII | Shell |
| 首词是命令，参数含非 ASCII + 有结构信号 | Shell |
| 首词是命令，参数含非 ASCII + 无结构信号 | Agent |
| `ai` 前缀 | Agent（强制） |

结构信号：`-`、`--`、`@`、`/`、`\`、`~`、`=`、`:`、引号、文件扩展名。跨语言通用，不需要枚举自然语言。

## 项目结构

```
iterm-agent/
├── iterm-agent.zsh            # zsh 插件（入口 + 路由）
├── install.sh                 # 一键安装脚本
├── pyproject.toml
└── iterm_agent/
    ├── quick.py               # CLI 入口（被 zsh 插件调用）
    ├── entry.py               # Agent 构建工厂
    ├── config.py              # 配置加载
    ├── session.py             # 会话持久化（文件锁）
    ├── core/
    │   ├── orchestrator.py    # 调度器
    │   ├── executor.py        # ReAct 执行器
    │   └── context.py         # 上下文构建
    ├── llm/
    │   ├── base.py            # LLM 抽象接口
    │   ├── openai_provider.py # OpenAI 兼容实现（流式 + 重试）
    │   └── factory.py         # Provider 工厂
    ├── guardrail/
    │   ├── engine.py          # 安全护栏（黑名单 + 确认）
    │   └── intent_guard.py    # 意图校验
    ├── memory/
    │   ├── long_term.py       # 长期记忆（JSON）
    │   └── compressor.py      # 上下文压缩
    └── tools/
        ├── registry.py        # 工具注册表
        ├── run_command.py     # 命令执行（超时 + 编码兼容）
        └── remember.py        # 记忆写入
```

## 日志

| 文件 | 内容 |
|------|------|
| `~/.iterm_agent/agent.log` | 运行日志（路由、LLM 调用、工具执行） |
| `~/.iterm_agent/audit.log` | 命令审计（每条命令及结果） |

## 开发

```bash
cd iterm-agent
PYTHONPATH=. python3 -m iterm_agent.quick "测试一下"
```

## License

MIT

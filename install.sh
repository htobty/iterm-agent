#!/usr/bin/env bash
set -e

ITERM_AGENT_HOME="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.iterm_agent"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

echo ""
echo "  iTerm Agent 安装"
echo "  ================="
echo ""

# 1. 检测 Python
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "  [错误] 未找到 Python >= 3.10，请先安装。"
    echo "         推荐: brew install python@3.12"
    exit 1
fi
echo "  ✓ Python: $PYTHON_BIN ($($PYTHON_BIN --version 2>&1 | awk '{print $2}'))"

# 2. 安装依赖
echo "  ✓ 安装依赖..."
"$PYTHON_BIN" -m pip install --quiet openai pyyaml rich 2>/dev/null || \
"$PYTHON_BIN" -m pip install --quiet --user openai pyyaml rich
echo "  ✓ 依赖就绪"

# 3. 配置
mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    echo "  ✓ 配置已存在: $CONFIG_FILE（跳过）"
else
    echo ""
    echo "  配置 LLM（直接回车使用默认值）："
    echo ""

    read -rp "  base_url [https://api.openai.com/v1]: " BASE_URL
    BASE_URL="${BASE_URL:-https://api.openai.com/v1}"

    read -rp "  model [gpt-4o]: " MODEL
    MODEL="${MODEL:-gpt-4o}"

    read -rp "  api_key: " API_KEY
    if [ -z "$API_KEY" ]; then
        echo "  [错误] api_key 不能为空"
        exit 1
    fi

    cat > "$CONFIG_FILE" <<EOF
llm:
  provider: openai
  model: $MODEL
  api_key: $API_KEY
  base_url: $BASE_URL
  temperature: 0.2
  max_tokens: 4096

agent:
  max_react_steps: 20
  auto_confirm: false

guardrail:
  enabled: true
  timeout: 30

memory:
  long_term_path: ~/.iterm_agent/memory.json
  max_facts: 50
EOF

    echo "  ✓ 配置已写入: $CONFIG_FILE"
fi

# 4. zshrc
ZSHRC="$HOME/.zshrc"
SOURCE_LINE="source $ITERM_AGENT_HOME/iterm-agent.zsh"

if [ -f "$ZSHRC" ] && grep -qF "iterm-agent.zsh" "$ZSHRC"; then
    echo "  ✓ zshrc 已配置（跳过）"
else
    echo "" >> "$ZSHRC"
    echo "# iTerm Agent" >> "$ZSHRC"
    echo "$SOURCE_LINE" >> "$ZSHRC"
    echo "  ✓ 已追加到 $ZSHRC"
fi

# 5. 完成
echo ""
echo "  ================="
echo "  安装完成！"
echo ""
echo "  重开 iTerm2 窗口即可使用。"
echo "  输入自然语言（如\"帮我安装 Python\"）或 ai 前缀触发 Agent。"
echo ""

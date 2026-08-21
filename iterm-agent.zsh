# iTerm Agent - zsh 插件
# 在 iTerm2 的 shell 中直接输入自然语言即可调用 Agent
#
# 安装：在 ~/.zshrc 末尾添加一行：
#   source ~/code/iterm-agent/iterm-agent.zsh
#
# 使用：
#   输入 "hi" 或 "帮我安装 Python" 按回车 → Agent 流式回复
#   输入 "ls -la" 按回车 → 正常执行
#   输入 "ai 帮我写个脚本" 按回车 → 强制走 Agent

# ===== 配置 =====
ITERM_AGENT_HOME="${ITERM_AGENT_HOME:-$HOME/code/iterm-agent}"
ITERM_AGENT_ENABLED="${ITERM_AGENT_ENABLED:-1}"
ITERM_AGENT_PREFIX="ai"

# ===== 内部函数 =====

# 判断输入是否应该走 Agent
_iterm_agent_should_intercept() {
    local input="$1"

    [[ -z "$input" ]] && return 1

    # ===== 快速路径：首字符是非 ASCII（中文、日文等）→ 一定是自然语言 =====
    local first_char="${input:0:1}"
    if [[ "$first_char" == [^[:ascii:]] ]]; then
        return 0
    fi

    # 注释、历史、子 shell → 不拦截
    [[ "$input" == \#* ]] && return 1
    [[ "$input" == \!* ]] && return 1
    [[ "$input" == \(* ]] && return 1

    # 包含 shell 语法 → 不拦截
    if [[ "$input" == *"|"* || "$input" == *">"* || "$input" == *"<"* || "$input" == *"&&"* || "$input" == *"||"* ]]; then
        return 1
    fi

    local first_word="${input%% *}"
    first_word="${first_word##*/}"

    [[ -z "$first_word" ]] && return 1
    [[ "$first_word" == [0-9]* ]] && return 1

    # 是系统命令 → 不拦截
    if command -v "$first_word" &>/dev/null; then
        return 1
    fi

    # 是 zsh 内建 → 不拦截
    case "$first_word" in
        cd|echo|export|set|unset|source|alias|unalias|bindkey|zle|typeset|declare|local|readonly|return|exit|exec|eval|wait|jobs|fg|bg|kill|trap|ulimit|umask|getopts|hash|history|fc|print|printf|read|select|time|true|false|test|let|shift|pushd|popd|dirs|pwd|type|which|where|whence|command|coproc|disable|enable|disown|emulate|float|integer|log|noglob|rehash|sched|setcap|setopt|unsetopt|var|vared|zcompile|zformat|zftp|zmodload|zparseopts|zprof|zpty|zregexparse|zsocket|zstyle|ztcp|autoload|builtin|caller|compadd|compcall|compdescribe|compfiles|compget|compquote|compscan|compset|compsub|comptry|compdump|compinit)
            return 1
            ;;
    esac

    # 是 zsh 函数 → 不拦截
    if typeset -f "$first_word" &>/dev/null; then
        return 1
    fi

    # 是别名 → 不拦截
    if alias "$first_word" &>/dev/null; then
        return 1
    fi

    # 不是已知命令 → 走 Agent
    return 0
}

# 调用 Agent（流式输出）
# $1: 输入内容
# $2: 是否强制 agent 模式（1=自然语言检测触发，0=ai 前缀触发保留路由）
_iterm_agent_run() {
    local input="$1"
    local force_agent="${2:-0}"

    local extra_flag=""
    if [[ "$force_agent" == "1" ]]; then
        extra_flag="--agent"
    fi

    # 直接执行 python -u（-u 禁用 stdout 缓冲，确保流式生效）
    (cd "$ITERM_AGENT_HOME" && PYTHONPATH=. python3 -u -m iterm_agent.quick $extra_flag "$input" 2>&1)

    # 结束后换行
    print ""
}

# 自定义 accept-line widget
_iterm_agent_accept_line() {
    local input="$BUFFER"

    # 未启用
    if [[ "$ITERM_AGENT_ENABLED" != "1" ]]; then
        zle .accept-line
        return
    fi

    # 强制前缀
    if [[ "$input" == "$ITERM_AGENT_PREFIX "* ]]; then
        local actual_input="${input#"$ITERM_AGENT_PREFIX "}"
        BUFFER=""
        _iterm_agent_run "$actual_input"
        zle reset-prompt
        return
    fi

    # 自然语言检测（强制 agent 模式，不再二次路由）
    if _iterm_agent_should_intercept "$input"; then
        BUFFER=""
        _iterm_agent_run "$input" 1
        zle reset-prompt
        return
    fi

    # 普通命令，正常执行
    zle .accept-line
}

# ===== 注册 =====
if [[ -n "$ZSH_VERSION" ]]; then
    zmodload zsh/zle 2>/dev/null
    zle -N _iterm_agent_accept_line
    bindkey '^M' _iterm_agent_accept_line
    bindkey '^J' _iterm_agent_accept_line
fi

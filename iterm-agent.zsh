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

# 判断参数部分是否包含命令结构信号（跨语言通用）
# 有结构信号 → 大概率是真正的命令参数
_iterm_agent_has_structural_signals() {
    local args="$1"

    # - 或 -- 开头的 flag
    [[ "$args" == *" -"* || "$args" == --* ]] && return 0
    # @ (user@host)
    [[ "$args" == *"@"* ]] && return 0
    # / 或 \ (路径)
    [[ "$args" == *"/"* || "$args" == *"\\"* ]] && return 0
    # ~ (home 路径)
    [[ "$args" == *"~"* ]] && return 0
    # = (VAR=val)
    [[ "$args" == *"="* ]] && return 0
    # : (host:port, drive letter)
    [[ "$args" == *":"* ]] && return 0
    # 引号包裹
    [[ "$args" == *"\""* || "$args" == *"'"* ]] && return 0
    # . 后跟字母（文件扩展名）
    [[ "$args" =~ '\.[a-zA-Z]' ]] && return 0

    return 1
}

# 判断输入是否应该走 Agent
_iterm_agent_should_intercept() {
    local input="$1"

    [[ -z "$input" ]] && return 1

    # 注释、历史、子 shell → 不拦截
    [[ "$input" == \#* ]] && return 1
    [[ "$input" == \!* ]] && return 1
    [[ "$input" == \(* ]] && return 1

    # 包含 shell 语法 → 不拦截
    if [[ "$input" == *"|"* || "$input" == *">"* || "$input" == *"<"* || "$input" == *"&&"* || "$input" == *"||"* || "$input" == *";"* ]]; then
        return 1
    fi

    local first_word="${input%% *}"
    first_word="${first_word##*/}"

    [[ -z "$first_word" ]] && return 1
    # 纯 ASCII 且以数字开头 → 可能是版本号/端口号等，不拦截
    # 含非 ASCII 则跳过此规则（如 "192.168.50.223就是我的台式机"）
    if [[ "$input" != *[^[:ascii:]]* && "$first_word" == [0-9]* ]]; then
        return 1
    fi

    # 判断首词是否是已知命令
    local is_command=0
    if command -v "$first_word" &>/dev/null; then
        is_command=1
    fi
    # zsh 内建
    if [[ "$is_command" == "0" ]]; then
        case "$first_word" in
            cd|pwd|export|source|unset|alias|unalias|bindkey|zle|typeset|declare|local|readonly|exit|exec|eval|jobs|fg|bg|trap|ulimit|umask|getopts|hash|history|fc|true|false|shift|pushd|popd|dirs|whence|command|coproc|disable|enable|disown|emulate|float|integer|log|noglob|rehash|sched|setcap|setopt|unsetopt|var|vared|zcompile|zformat|zftp|zmodload|zparseopts|zprof|zpty|zregexparse|zsocket|zstyle|ztcp|autoload|builtin|caller|compadd|compcall|compdescribe|compfiles|compget|compquote|compscan|compset|compsub|comptry|compdump|compinit)
                is_command=1
                ;;
        esac
    fi
    # zsh 函数
    if [[ "$is_command" == "0" ]] && typeset -f "$first_word" &>/dev/null; then
        is_command=1
    fi
    # 别名
    if [[ "$is_command" == "0" ]] && alias "$first_word" &>/dev/null; then
        is_command=1
    fi

    # 首词不是已知命令 → Agent
    if [[ "$is_command" == "0" ]]; then
        return 0
    fi

    # 首词是已知命令：
    # 参数纯 ASCII → Shell（无歧义）
    local args="${input#"$first_word"}"
    args="${args# }"
    if [[ "$args" != *[^[:ascii:]]* ]]; then
        return 1
    fi

    # 参数含非 ASCII：检查结构信号
    if _iterm_agent_has_structural_signals "$args"; then
        return 1  # 有结构信号 → Shell
    fi

    # 无结构信号 → Agent（大概率是自然语言提问）
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

    # 确保退出码为 0，不影响 iTerm2 箭头颜色
    return 0
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

# Bash completion for vidcapture
# Install: vidcapture completion bash --install
# Or: vidcapture completion bash > ~/.local/share/bash-completion/completions/vidcapture

_vidcapture_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Handle 'completion' subcommand
    if [[ "${COMP_WORDS[1]}" == "completion" ]]; then
        case "$COMP_CWORD" in
            2)
                COMPREPLY=($(compgen -W "bash" -- "$cur"))
                ;;
            *)
                COMPREPLY=($(compgen -W "--install --path" -- "$cur"))
                ;;
        esac
        return 0
    fi

    # Flags requiring directory argument
    case "$prev" in
        -o|--output)
            compopt -o nospace
            local IFS=$'\n'

            if [[ "$cur" == /* ]] || [[ "$cur" == ~* ]]; then
                # Absolute path - expand ~ and complete filesystem
                local search_path="${cur/#\~/$HOME}"
                COMPREPLY=($(compgen -d -- "$search_path" 2>/dev/null))
            else
                # Vault-relative - complete from vault directory
                local vault=""
                if [[ -f ~/.ytcapture.yml ]]; then
                    vault=$(awk '/^vault:/ {print $2}' ~/.ytcapture.yml 2>/dev/null | tr -d "\"'")
                    # Expand ~ and environment variables like $HOME
                    vault="${vault/#\~/$HOME}"
                    vault=$(eval echo "$vault" 2>/dev/null)
                fi
                if [[ -n "$vault" && -d "$vault" ]]; then
                    COMPREPLY=($(cd "$vault" && compgen -d -- "$cur" 2>/dev/null))
                else
                    COMPREPLY=($(compgen -d -- "$cur" 2>/dev/null))
                fi
            fi
            COMPREPLY=("${COMPREPLY[@]/%//}")
            return 0
            ;;
        --interval|--max-frames|--dedup-threshold)
            # Numeric arguments, no completion
            return 0
            ;;
        --frame-format)
            COMPREPLY=($(compgen -W "jpg png" -- "$cur"))
            return 0
            ;;
    esac

    # Flag completion
    if [[ "$cur" == -* ]]; then
        local opts="-o --output --interval --max-frames --frame-format --dedup-threshold --no-dedup --fast --json -v --verbose --version -h --help"
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        return 0
    fi

    # Subcommand completion at position 1
    if [[ "$COMP_CWORD" -eq 1 ]] && [[ "completion" == "$cur"* ]]; then
        COMPREPLY=("completion")
        return 0
    fi

    # Default: video file completion
    compopt -o default
    COMPREPLY=()
}

complete -F _vidcapture_completions vidcapture

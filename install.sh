#!/usr/bin/env bash
# memory-tool-conformance — interactive install wizard.
set -euo pipefail

if [ -t 1 ]; then C_BOLD="$(tput bold)"; C_RESET="$(tput sgr0)"; C_GREEN="$(tput setaf 2)"; C_YELLOW="$(tput setaf 3)"; C_RED="$(tput setaf 1)"; else C_BOLD=""; C_RESET=""; C_GREEN=""; C_YELLOW=""; C_RED=""; fi
say()  { printf "%s%s%s\n" "$C_BOLD" "$1" "$C_RESET"; }
info() { printf "  %s\n" "$1"; }
ok()   { printf "  %s✓%s %s\n" "$C_GREEN" "$C_RESET" "$1"; }
warn() { printf "  %s!%s %s\n" "$C_YELLOW" "$C_RESET" "$1"; }
fail() { printf "  %s✗%s %s\n" "$C_RED" "$C_RESET" "$1" >&2; exit 1; }
prompt_yn() { local q="$1" def="${2:-y}" ans; if [ "$def" = "y" ]; then read -r -p "  $q [Y/n]: " ans; ans="${ans:-y}"; else read -r -p "  $q [y/N]: " ans; ans="${ans:-n}"; fi; [[ "$ans" =~ ^[Yy] ]]; }
prompt_default() { read -r -p "  $1 [$2]: " ans; echo "${ans:-$2}"; }

detect_os() { OS_ID=unknown; OS_LIKE=""; OS_VERSION=""; OS_WSL=0; [ -f /etc/os-release ] && { . /etc/os-release; OS_ID="${ID:-}"; OS_LIKE="${ID_LIKE:-}"; OS_VERSION="${VERSION_ID:-}"; }; [ "$(uname)" = "Darwin" ] && OS_ID=macos; grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null && OS_WSL=1 || true; }
pkg_install() {
    # Caller is responsible for prompting the user (see ensure_python). This
    # function prints the exact command before running so the user can audit
    # / abort with Ctrl-C. Uses an array (not eval) to avoid shell-injection
    # surface if a future caller passes user-influenced package names.
    local -a cmd
    case "$OS_ID" in
        debian|ubuntu)
            info "running: sudo apt-get update -qq && sudo apt-get install -y $*"
            sudo apt-get update -qq && sudo apt-get install -y "$@"
            return $?
            ;;
        fedora|rhel|centos) cmd=(sudo dnf install -y "$@");;
        arch|manjaro)       cmd=(sudo pacman -S --noconfirm "$@");;
        alpine)             cmd=(sudo apk add --no-cache "$@");;
        opensuse*|sles)     cmd=(sudo zypper install -y "$@");;
        macos)              cmd=(brew install "$@");;
        *) warn "unknown OS — install manually: $*"; return 1;;
    esac
    info "running: ${cmd[*]}"
    "${cmd[@]}"
}
ensure_python() {
    command -v python3 >/dev/null && {
        local pyv; pyv="$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
        case "$pyv" in 3.1[0-9]|3.[2-9][0-9]) ok "Python $pyv"; return 0;; esac
    }
    if prompt_yn "Install Python 3.10+ via system package manager?"; then
        case "$OS_ID" in
            debian|ubuntu) pkg_install python3 python3-venv python3-pip;;
            fedora|rhel|centos) pkg_install python3 python3-pip;;
            arch|manjaro) pkg_install python python-pip;;
            alpine) pkg_install python3 py3-pip;;
            macos) pkg_install python@3.12;;
            *) fail "install Python 3.10+ manually then re-run";;
        esac
    else fail "Python 3.10+ required"; fi
}

main() {
    say "memory-tool-conformance — install wizard"
    detect_os
    info "OS: ${OS_ID}${OS_VERSION:+ $OS_VERSION}$([ "$OS_WSL" = 1 ] && echo ' (WSL2)')"

    say ""; say "Step 1/3: Python 3.10+"; ensure_python

    say ""; say "Step 2/3: Install"
    local INSTALL_HOME; INSTALL_HOME="$(prompt_default "Install root" "$HOME/.local/share/memory-tool-conformance")"
    mkdir -p "$INSTALL_HOME"
    if [ -d "$INSTALL_HOME/.git" ]; then ( cd "$INSTALL_HOME" && git pull -q ); else git clone -q https://github.com/M00C1FER/memory-tool-conformance.git "$INSTALL_HOME"; fi
    cd "$INSTALL_HOME"
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -e .[dev]
    local BIN="${HOME}/.local/bin"; mkdir -p "$BIN"
    cat > "$BIN/memory-conformance" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_HOME/.venv/bin/memory-conformance" "\$@"
EOF
    chmod +x "$BIN/memory-conformance"
    ok "installed"

    say ""; say "Step 3/3: Verify (run conformance suite against bundled reference impl)"
    if "$BIN/memory-conformance" >/dev/null 2>&1; then
        ok "reference implementation passes 10/10 conformance"
    else
        warn "verification command exited non-zero — see 'memory-conformance' output"
    fi
    say ""
    ok "Done. Run: memory-conformance --target your_pkg.module:make_server --name my-server"
}
main "$@"

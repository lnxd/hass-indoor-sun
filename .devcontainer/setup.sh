#!/usr/bin/env bash
set -Eeuo pipefail

# helpers
SUDO=''
((EUID)) && SUDO='sudo'
export DEBIAN_FRONTEND=noninteractive
repo_dir="$(git rev-parse --show-toplevel 2> /dev/null || pwd)"
cd "$repo_dir"

# locale & tz (for VS Code)
$SUDO locale-gen en_US.UTF-8
echo 'export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LANGUAGE=en_US.UTF-8' >> "$HOME/.zshrc"
$SUDO ln -sf /usr/share/zoneinfo/Australia/Melbourne /etc/localtime

# uv (fast PEP 723)
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | bash -s -- --quiet
fi
echo 'export PATH="$HOME/.local/bin:$PATH"
export UV_HTTP_TIMEOUT=60
export UV_STACK_SIZE=8388608
export UV_NO_INSTALLER_METADATA=1' >> "$HOME/.zshrc"
export PATH="$HOME/.local/bin:$PATH"

# Python env (uv)
echo "→ creating .venv with uv…"
uv venv .venv
uv sync --reinstall

cat >> "$HOME/.zshrc" << EOF
# auto-activate venv
cd "$repo_dir" 2>/dev/null || true
[ -f "$repo_dir/.venv/bin/activate" ] && source "$repo_dir/.venv/bin/activate"
EOF

cat >> "$HOME/.bashrc" << EOF
# auto-activate venv
cd "$repo_dir" 2>/dev/null || true
[ -f "$repo_dir/.venv/bin/activate" ] && source "$repo_dir/.venv/bin/activate"
EOF

cat >> "$HOME/.bash_profile" << EOF
# Source .bashrc and activate venv for login shells
[ -f ~/.bashrc ] && source ~/.bashrc
cd "$repo_dir" 2>/dev/null || true
[ -f "$repo_dir/.venv/bin/activate" ] && source "$repo_dir/.venv/bin/activate"
EOF

# Oh-My-Zsh plugins
zshrc="$HOME/.zshrc"
grep -qE '^\s*plugins=\(' "$zshrc" || echo 'plugins=()' >> "$zshrc"
required_plugins=(
    history-substring-search
    dotenv
    git
    gh
    python
    vscode
)
current=$(grep -E '^\s*plugins=\(' "$zshrc" | head -n1 | sed -E 's/.*\((.*)\).*/\1/')
for p in "${required_plugins[@]}"; do
    [[ " $current " =~ " $p " ]] || current+=" $p"
done
current=$(echo "$current" | xargs)
sed -i -E "0,/^\s*plugins=\(.*$/s//plugins=(${current})/" "$zshrc"

if ! grep -q 'history-substring-search-up' "$zshrc"; then
    cat >> "$zshrc" << 'ZHSUB'
# ── history-substring-search ↑ / ↓ ──
zmodload zsh/terminfo 2>/dev/null || true
bindkey "${terminfo[kcuu1]:-^[[A}" history-substring-search-up
bindkey "${terminfo[kcud1]:-^[[B}" history-substring-search-down
ZHSUB
fi

# screen config
screenrc="$HOME/.screenrc"
grep -q 'ti@:te@' "$screenrc" || cat >> "$screenrc" << 'SCREENSUB'
defscrollback 10000                # ~10 k lines per window
termcapinfo xterm* ti@:te@         # keep host scroll-back & mouse wheel
SCREENSUB

# Finished!
echo "DevContainer bootstrap complete!"

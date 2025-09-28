#!/usr/bin/env bash
set -euo pipefail

# ------------------------------
# Configurable paths & constants
# ------------------------------
WORKSPACE="/workspaces/slip_stick"
CODEX_DIR="$WORKSPACE/.codex"
CODEX_CFG="$CODEX_DIR/config.toml"
GITHUB_ENV="$CODEX_DIR/github.env"
LOG="$HOME/postCreate.log"

VSC_DATA_ROOTS=(
  "$HOME/.vscode-server/data"
  "$HOME/.vscode-remote/data"
  "$HOME/.vscode-server-insiders/data"
  "$HOME/.vscode-remote-insiders/data"
)

DOCKER_CMD="/usr/bin/docker"
[[ -x "$DOCKER_CMD" ]] || DOCKER_CMD="docker"

# -----------
# Mini logger
# -----------
log()  { echo "[$(date -Is)] $*" | tee -a "$LOG" ; }
warn() { log "WARN: $*" ; }
ok()   { log "✅ $*" ; }

log "=== postCreate START ==="
log "whoami=$(whoami)"
log "pwd=$(pwd)"
log "PATH=$PATH"
(node -v && npm -v) 2>&1 | tee -a "$LOG" || true

# ------------------------------------------------------------
# Docker socket access: align group with host /var/run/docker.sock
# ------------------------------------------------------------
{
  SOCK="/var/run/docker.sock"
  if [ -S "$SOCK" ]; then
    GID="$(stat -c '%g' "$SOCK")"
    log "docker.sock detected (gid=$GID)"

    # Find or create a group with that GID
    HOST_GRP="$(getent group | awk -F: -v g="$GID" '$3==g{print $1; exit}')"
    if [ -z "${HOST_GRP:-}" ]; then
      if getent group docker >/dev/null 2>&1; then
        CUR_GID="$(getent group docker | cut -d: -f3)"
        if [ "$CUR_GID" = "$GID" ]; then
          HOST_GRP="docker"
        else
          HOST_GRP="dockersock-$GID"
          sudo groupadd -g "$GID" "$HOST_GRP" || true
        fi
      else
        HOST_GRP="docker"
        sudo groupadd -g "$GID" "$HOST_GRP" || true
      fi
    fi

    # Add current user to that group (idempotent)
    if id -nG "$USER" | tr ' ' '\n' | grep -qx "$HOST_GRP"; then
      ok "User '$USER' already in group '$HOST_GRP'"
    else
      sudo usermod -aG "$HOST_GRP" "$USER"
      ok "Added '$USER' to group '$HOST_GRP'"
    fi

    # Ensure the socket is group-readable/writable
    sudo chown :"$GID" "$SOCK" || true
    sudo chmod g+rw "$SOCK" || true

    log "docker.sock perms: $(ls -l "$SOCK")"
    log "user groups now:  $(id -nG)"
    log "NOTE: If docker still says 'permission denied', reopen the devcontainer window to refresh group membership."
  else
    warn "No $SOCK found; skipping docker socket setup."
  fi
} || warn "Docker socket setup failed (continuing)"

# -----------------------------------------------
# Codex config & secret handling
# -----------------------------------------------
mkdir -p "$CODEX_DIR"

if [[ -n "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  printf 'GITHUB_PERSONAL_ACCESS_TOKEN=%s\n' "$GITHUB_PERSONAL_ACCESS_TOKEN" > "$GITHUB_ENV"
  chmod 600 "$GITHUB_ENV"
  ok "GitHub token written to $GITHUB_ENV"
else
  warn "GITHUB_PERSONAL_ACCESS_TOKEN not set in containerEnv"
fi

if [[ ! -f "$CODEX_CFG" ]]; then
  cat > "$CODEX_CFG" <<'EOF'
projects = { "/workspaces/slip_stick" = { trust_level = "trusted" } }

[mcp_servers.github]
command = "/usr/bin/docker"
args = [
  "run","-i","--rm",
  "--env-file","/workspaces/slip_stick/.codex/github.env",
  "ghcr.io/github/github-mcp-server"
]
EOF
  ok "Wrote $CODEX_CFG"
else
  log "$CODEX_CFG already exists; leaving as-is"
fi

# -------------------------------------------------------
# Generate Cline MCP settings
# -------------------------------------------------------
{
  read -r -d '' CLINE_JSON <<EOF || true
{
  "mcpServers": {
    "github": {
      "command": "$DOCKER_CMD",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "$GITHUB_ENV",
        "ghcr.io/github/github-mcp-server"
      ],
      "disabled": false,
      "autoApprove": [
        "add_comment_to_pending_review"
      ]
    },
    "duckduckgo": {
      "command": "$DOCKER_CMD",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/duckduckgo"
      ],
      "disabled": false,
      "autoApprove": [
        "search"
      ]
    },
    "codex": {
      "command": "codex",
      "args": [
        "mcp"
      ],
      "disabled": false,
      "autoApprove": [
        "codex"
      ]
    },
    "magg": {
      "command": "$DOCKER_CMD",
      "args": [
        "run",
        "-i",
        "--rm",
        "ghcr.io/sitbon/magg:latest",
        "magg",
        "serve"
      ],
      "disabled": false,
      "autoApprove": [
        "magg_reload_config",
        "proxy"
      ]
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/workspaces/slip_stick"
      ],
      "disabled": false,
      "autoApprove": [
        "list_allowed_directories",
        "directory_tree",
        "read_file"
      ]
    },
    "github.com/upstash/context7-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@upstash/context7-mcp"
      ],
      "disabled": false,
      "autoApprove": [
        "get-library-docs"
      ]
    },
    "github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking": {
      "command": "$DOCKER_CMD",
      "args": [
        "run",
        "--rm",
        "-i",
        "mcp/sequentialthinking"
      ],
      "disabled": false,
      "autoApprove": [
        "sequential_thinking"
      ]
    }
  }
}
EOF

  wrote_any=false
  for ROOT in "${VSC_DATA_ROOTS[@]}"; do
    DEST="$ROOT/User/globalStorage/saoudrizwan.claude-dev/settings"
    mkdir -p "$DEST" 2>/dev/null || true
    if [[ -d "$ROOT" && ! -w "$DEST" && $(id -u) -ne 0 && $(command -v sudo >/dev/null 2>&1; echo $?) -eq 0 ]]; then
      sudo chown -R "$(id -u)":"$(id -g)" "$ROOT" 2>/dev/null || true
    fi
    if [[ -d "$ROOT" ]]; then
      mkdir -p "$DEST"
      printf '%s\n' "$CLINE_JSON" > "$DEST/cline_mcp_settings.json"
      ok "Cline MCP config written to $DEST/cline_mcp_settings.json"
      wrote_any=true
    fi
  done

  if [[ "$wrote_any" == false ]]; then
    log "VS Code server data folder not found yet; will populate on next attach/rebuild."
  fi
} || warn "Failed to generate Cline MCP settings (continuing)"

# ---------------------------------
# Ensure custom .bashrc env + wrappers (idempotent)
# ---------------------------------
RC="$HOME/.bashrc"
if ! grep -q "__CLINE_DONE__" "$RC" 2>/dev/null; then
  cat >> "$RC" <<'EOF'

# theme-like prompt bits
__bash_prompt() {
    local userpart='`export XIT=$? \
        && [ ! -z "${GITHUB_USER:-}" ] && echo -n "\[\033[0;32m\]@${GITHUB_USER:-} " || echo -n "\[\033[0;32m\]\u " \
        && [ "$XIT" -ne "0" ] && echo -n "\[\033[1;31m\]➜" || echo -n "\[\033[0m\]➜"`'
    local gitbranch='`\
        if [ "$(git config --get devcontainers-theme.hide-status 2>/dev/null)" != 1 ] && [ "$(git config --get codespaces-theme.hide-status 2>/dev/null)" != 1 ]; then \
            export BRANCH="$(git --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || git --no-optional-locks rev-parse --short HEAD 2>/dev/null)"; \
            if [ "${BRANCH:-}" != "" ]; then \
                echo -n "\[\033[0;36m\](\[\033[1;31m\]${BRANCH:-}" \
                && if [ "$(git config --get devcontainers-theme.show-dirty 2>/dev/null)" = 1 ] && \
                    git --no-optional-locks ls-files --error-unmatch -m --directory --no-empty-directory -o --exclude-standard ":/*" > /dev/null 2>&1; then \
                        echo -n " \[\033[1;33m\]✗"; \
                fi \
                && echo -n "\[\033[0;36m\]) "; \
            fi; \
        fi`'
    local lightblue='\[\033[1;34m\]'
    local removecolor='\[\033[0m\]'
    PS1="${userpart} ${lightblue}\w ${gitbranch}${removecolor}\$ "
    unset -f __bash_prompt
}
__bash_prompt
export PROMPT_DIRTRIM=4

# Avoid DEBUG/prompt hooks in VS Code terminals
if [[ -n "$CLINE_AGENT" || "$TERM_PROGRAM" == "vscode" ]]; then
  PS1='\u@\h:\w\$ '
  PROMPT_COMMAND=
fi

# --- Cline minimal env in VS Code terminals ---
if [[ -z "$CLINE_AGENT" && "$TERM_PROGRAM" == "vscode" ]]; then
  export CLINE_AGENT=1
fi

# PATH shims
export PATH="$HOME/.local/bin:$PATH"

# ---------- Cline hardened runners ----------
# Quick terminal rescue
alias fixterm='stty sane; tput reset || reset'

# Default runner: clean shell, line-buffered, no input, always emits sentinel to stdout+stderr
cline() {
  local cmd="$*"
  stdbuf -oL -eL bash --noprofile --norc -lc "$cmd" </dev/null
  local code=$?
  stty sane 2>/dev/null || true
  printf '\n__CLINE_DONE__:%s\n' "$code" | tee /dev/stderr >/dev/null
  return 0
}

# Bounded runner: kills after N seconds (default 600)
clinet() {
  local secs="${1:-600}"; shift
  local cmd="$*"
  timeout --preserve-status "${secs}s" bash --noprofile --norc -lc "$cmd" </dev/null
  local code=$?
  stty sane 2>/dev/null || true
  printf '\n__CLINE_DONE__:%s\n' "$code" | tee /dev/stderr >/dev/null
  return 0
}

# Force PTY capture (for tools that mangle the TTY)
clines() {
  local cmd="$*"
  local quoted; quoted=$(printf '%q' "$cmd")
  script -q -c "stdbuf -oL -eL bash --noprofile --norc -lc $quoted" /dev/null
  local code=$?
  stty sane 2>/dev/null || true
  printf '\n__CLINE_DONE__:%s\n' "$code" | tee /dev/stderr >/dev/null
  return 0
}
EOF
  ok "Appended custom .bashrc configurations"
else
  log "~/.bashrc already has custom configurations"
fi

# ---------------------------------
# Node tooling: keep nvm-compatible (no global npm/prefix)
# ---------------------------------
# 1) Remove incompatible npmrc entries if present
if [[ -f "$HOME/.npmrc" ]]; then
  sed -i.bak '/^prefix\s*=.*/d;/^globalconfig\s*=.*/d' "$HOME/.npmrc" || true
fi
# 2) Ensure ~/.local/bin is on PATH for our shims
grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" 2>/dev/null || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
mkdir -p "$HOME/.local/bin"

# 3) Codex & Gemini runners via npx (no global installs)
cat > "$HOME/.local/bin/codex" <<'EOS'
#!/usr/bin/env bash
exec npx -y @openai/codex "$@"
EOS
chmod +x "$HOME/.local/bin/codex"

cat > "$HOME/.local/bin/gemini" <<'EOS'
#!/usr/bin/env bash
exec npx -y @google/gemini-cli "$@"
EOS
chmod +x "$HOME/.local/bin/gemini"

[[ -e "$HOME/.codex" ]] || ln -s "$CODEX_DIR" "$HOME/.codex"

log "codex path: $(command -v codex || echo missing)"
(codex --version 2>&1 | tee -a "$LOG") || true

# ---------------------------------
# Install project dependencies
# ---------------------------------
log "Installing project dependencies and dev tooling..."
python3.12 -m pip install -U pip setuptools wheel || true
if [[ -f requirements-dev.txt ]]; then
  pip install -r requirements-dev.txt || warn "requirements-dev.txt install failed"
else
  log "requirements-dev.txt not found; installing dev tools directly"
  python3.12 -m pip install black ruff mypy pytest bandit pip-audit pre-commit || warn "tooling install had issues"
fi
pip install -e . || warn "Editable install failed (check pyproject/ setup.cfg)"

# Initialize pre-commit hooks if config exists
if [[ -f .pre-commit-config.yaml ]]; then
  pre-commit install || warn "pre-commit install failed"
  pre-commit run --all-files || true
else
  log ".pre-commit-config.yaml not found (skipping hooks)"
fi

ok "Project dependencies installed"
touch "$HOME/.postcreate_ran"
log "=== postCreate END ==="

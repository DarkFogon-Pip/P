#!/usr/bin/env bash
# update-openclaw.sh
#
# Workaround for `openclaw update` failing with ECONNRESET in WSL.
#
# Root cause: openclaw's built-in updater runs `npm i -g openclaw@<tag>`
# exactly once with no retry.  WSL2's virtual network adapter can reset
# TCP connections (errno -104 / ECONNRESET), causing the single attempt
# to fail.  This script applies WSL-friendly npm network settings and
# retries the install with exponential back-off.
#
# Usage:
#   bash scripts/update-openclaw.sh          # update to latest stable
#   bash scripts/update-openclaw.sh beta      # update to beta channel
#   bash scripts/update-openclaw.sh 2026.2.17 # pin to specific version

set -euo pipefail

# ── configuration ────────────────────────────────────────────────────────────
CHANNEL="${1:-latest}"
MAX_ATTEMPTS=5
BASE_DELAY=2          # seconds; doubles each attempt (2, 4, 8, 16, 32)
NPM_NETWORK_TIMEOUT=300000  # 5 min — default is only 30 s, too short for WSL

# Resolve the dist-tag / version spec
case "$CHANNEL" in
  stable|latest) SPEC="openclaw@latest" ;;
  beta)          SPEC="openclaw@beta"   ;;
  *)             SPEC="openclaw@${CHANNEL}" ;;
esac

# ── apply WSL-resilient npm settings (project-local .npmrc-style env vars) ──
# These are passed as environment overrides so they don't mutate the user's
# global npm config permanently.
export npm_config_network_timeout="$NPM_NETWORK_TIMEOUT"
export npm_config_fetch_retry_mintimeout=20000   # min wait between retries
export npm_config_fetch_retry_maxtimeout=120000  # max wait between retries
export npm_config_fetch_retries=3               # npm's own retry count
export npm_config_maxsockets=3                  # fewer parallel sockets → fewer resets

# IPv6 can cause ECONNRESET in some WSL2 builds; prefer IPv4
export npm_config_prefer_ipv4=true 2>/dev/null || true

# ── helper ────────────────────────────────────────────────────────────────────
log()  { printf '\033[1;34m[openclaw-update]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[openclaw-update]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[openclaw-update]\033[0m %s\n' "$*" >&2; }

# ── detect package manager ────────────────────────────────────────────────────
detect_manager() {
  # Check how openclaw is globally installed; prefer the same manager.
  if command -v pnpm &>/dev/null; then
    local root
    root=$(pnpm root -g 2>/dev/null) || true
    if [[ -d "${root}/openclaw" ]]; then
      echo "pnpm"; return
    fi
  fi
  echo "npm"
}

install_with_npm() {
  local spec="$1"
  npm install -g "$spec" \
    --network-timeout "$NPM_NETWORK_TIMEOUT" \
    --prefer-online
}

install_with_pnpm() {
  local spec="$1"
  pnpm add -g "$spec"
}

# ── main retry loop ───────────────────────────────────────────────────────────
MANAGER=$(detect_manager)
log "Detected package manager: $MANAGER"
log "Installing: $SPEC"
log ""

attempt=1
delay=$BASE_DELAY

while (( attempt <= MAX_ATTEMPTS )); do
  log "Attempt $attempt / $MAX_ATTEMPTS …"

  if [[ "$MANAGER" == "pnpm" ]]; then
    install_with_pnpm "$SPEC" && break
  else
    install_with_npm "$SPEC" && break
  fi

  EXIT_CODE=$?

  if (( attempt == MAX_ATTEMPTS )); then
    err "All $MAX_ATTEMPTS attempts failed (last exit code: $EXIT_CODE)."
    err ""
    err "Additional WSL network fixes to try manually:"
    err "  1. Flush WSL DNS:  sudo sh -c 'echo nameserver 8.8.8.8 > /etc/resolv.conf'"
    err "  2. Reset Winsock (in PowerShell as Admin): netsh winsock reset"
    err "  3. Restart WSL:    wsl --shutdown  (then reopen)"
    err "  4. Use a proxy:    npm config set proxy http://your-proxy:port"
    exit "$EXIT_CODE"
  fi

  warn "Attempt $attempt failed (ECONNRESET or similar). Retrying in ${delay}s …"
  sleep "$delay"
  delay=$(( delay * 2 ))
  (( attempt++ ))
done

log ""
log "Update complete!"
log "Installed version: $(openclaw --version 2>/dev/null || echo 'unknown')"

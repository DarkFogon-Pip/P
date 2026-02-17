#!/usr/bin/env bash
# Setup script for OpenAI Codex CLI on Ubuntu (WSL)
set -euo pipefail

echo "=== Codex CLI Setup for Ubuntu on WSL ==="

# ── 1. Check we are on Ubuntu ──────────────────────────────────────────────
if ! grep -qi ubuntu /etc/os-release 2>/dev/null; then
  echo "Warning: This script is designed for Ubuntu. Proceeding anyway..."
fi

# ── 2. System dependencies ─────────────────────────────────────────────────
echo ""
echo "[1/4] Updating apt and installing prerequisites..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl git build-essential

# ── 3. Node.js via nvm (recommended for WSL) ───────────────────────────────
echo ""
echo "[2/4] Setting up Node.js..."

if command -v node &>/dev/null; then
  NODE_VERSION=$(node --version)
  echo "  Node.js already installed: $NODE_VERSION"
  # Codex CLI requires Node 22+
  NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
  if [ "$NODE_MAJOR" -lt 22 ]; then
    echo "  Node.js $NODE_VERSION is too old (need v22+). Installing via nvm..."
    INSTALL_NODE=true
  else
    INSTALL_NODE=false
  fi
else
  echo "  Node.js not found. Installing via nvm..."
  INSTALL_NODE=true
fi

if [ "$INSTALL_NODE" = true ]; then
  # Install nvm
  if [ ! -d "$HOME/.nvm" ]; then
    echo "  Installing nvm..."
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  fi

  # Load nvm into current shell
  export NVM_DIR="$HOME/.nvm"
  # shellcheck source=/dev/null
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

  echo "  Installing Node.js 22 (LTS)..."
  nvm install 22
  nvm use 22
  nvm alias default 22
  echo "  Node.js $(node --version) installed."
else
  echo "  Using existing Node.js: $(node --version)"
fi

# Make sure npm is available
if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Please re-run the script or install npm manually."
  exit 1
fi

echo "  npm version: $(npm --version)"

# ── 4. Install Codex CLI ───────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Codex CLI (@openai/codex)..."
npm install -g @openai/codex

echo ""
echo "  Codex CLI version: $(codex --version 2>/dev/null || echo 'installed')"

# ── 5. Configure API key ───────────────────────────────────────────────────
echo ""
echo "[4/4] Configuring OpenAI API key..."

SHELL_RC=""
if [ -n "${ZSH_VERSION:-}" ] || [ "$SHELL" = "/bin/zsh" ]; then
  SHELL_RC="$HOME/.zshrc"
elif [ -n "${BASH_VERSION:-}" ] || [ "$SHELL" = "/bin/bash" ]; then
  SHELL_RC="$HOME/.bashrc"
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo ""
  echo "  OPENAI_API_KEY is not set."
  echo "  Get your key at: https://platform.openai.com/api-keys"
  echo ""
  read -rp "  Enter your OpenAI API key (or press Enter to skip): " USER_KEY
  if [ -n "$USER_KEY" ]; then
    export OPENAI_API_KEY="$USER_KEY"
    if [ -n "$SHELL_RC" ]; then
      # Remove any old entry first
      grep -v "OPENAI_API_KEY" "$SHELL_RC" > "${SHELL_RC}.tmp" && mv "${SHELL_RC}.tmp" "$SHELL_RC"
      echo "export OPENAI_API_KEY=\"$USER_KEY\"" >> "$SHELL_RC"
      echo "  API key saved to $SHELL_RC"
    fi
  else
    echo "  Skipped. Set it later with:"
    echo "    export OPENAI_API_KEY=\"sk-...\""
    if [ -n "$SHELL_RC" ]; then
      echo "  Then add that line to $SHELL_RC"
    fi
  fi
else
  echo "  OPENAI_API_KEY is already set in environment."
fi

# ── nvm shell integration reminder ────────────────────────────────────────
if [ "${INSTALL_NODE:-false}" = true ] && [ -n "$SHELL_RC" ]; then
  if ! grep -q "NVM_DIR" "$SHELL_RC"; then
    echo "" >> "$SHELL_RC"
    echo '# nvm' >> "$SHELL_RC"
    echo 'export NVM_DIR="$HOME/.nvm"' >> "$SHELL_RC"
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> "$SHELL_RC"
    echo '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> "$SHELL_RC"
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  Codex CLI setup complete!"
echo "========================================="
echo ""
echo "Quick start:"
echo "  codex                         # interactive mode"
echo "  codex \"explain this repo\"     # one-shot prompt"
echo "  codex --help                  # all options"
echo ""
if [ "${INSTALL_NODE:-false}" = true ]; then
  echo "NOTE: nvm was installed. Restart your terminal (or run 'source ~/$( basename "${SHELL_RC:-".bashrc"}") ') to use 'codex' in future sessions."
  echo ""
fi

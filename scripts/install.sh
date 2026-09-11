#!/usr/bin/env bash
# Install the latest launchpad-axi single-file build onto your PATH.
# Needs curl and a Python 3.10+ interpreter. No gh CLI, no token (public repo).
#
#   curl -fsSL https://raw.githubusercontent.com/craig-ai-tooling/launchpad-axi/main/scripts/install.sh | bash
#   BIN=/usr/local/bin/launchpad-axi ./scripts/install.sh   # custom target
set -euo pipefail

REPO="craig-ai-tooling/launchpad-axi"
BIN="${BIN:-$HOME/.local/bin/launchpad-axi}"
URL="https://github.com/${REPO}/releases/latest/download/launchpad-axi.pyz"

mkdir -p "$(dirname "$BIN")"
curl -fsSL "$URL" -o "$BIN"
chmod +x "$BIN"
"$BIN" --help >/dev/null
echo "installed $BIN"

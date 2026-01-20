#!/bin/bash
# Installation script for mc-cli

set -e

VENV_DIR="$HOME/bin/py_env_mc-cli"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing mc-cli..."

# Create virtual environment
echo "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

# Install package in editable mode
echo "Installing mc-cli package..."
"$VENV_DIR/bin/pip" install -e "$REPO_DIR"

# Create symlink
echo "Creating symlink in ~/bin..."
mkdir -p "$HOME/bin"
ln -sf "$REPO_DIR/mc" "$HOME/bin/mc"

echo ""
echo "Installation complete!"
echo ""
echo "Make sure ~/bin is in your PATH:"
echo "  export PATH=\"\$HOME/bin:\$PATH\""
echo ""
echo "You can now run: mc -h"

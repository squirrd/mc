#!/bin/sh
# MC CLI installer
# Usage: curl -LsSf https://raw.githubusercontent.com/squirrd/mc/refs/heads/main/install.sh | sh

set -e

MC_REPO="git+https://github.com/squirrd/mc"

say() {
    printf "mc-installer: %s\n" "$1"
}

err() {
    printf "mc-installer: error: %s\n" "$1" >&2
    exit 1
}

# Ensure uv is available
ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        say "uv found: $(uv --version)"
        return
    fi

    err "uv is required but not installed. Please install it first: https://docs.astral.sh/uv/getting-started/installation/"
}

# Install mc via uv tool
install_mc() {
    say "Installing MC CLI..."
    uv tool install "$MC_REPO"
    say "MC CLI installed."
}

check_path() {
    # uv tool binaries land in ~/.local/bin (Linux/macOS)
    UV_TOOL_BIN="$HOME/.local/bin"
    case ":$PATH:" in
        *":$UV_TOOL_BIN:"*) ;;
        *)
            say ""
            say "NOTE: $UV_TOOL_BIN is not in your PATH."
            say "Add the following to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
            say ""
            say "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            say ""
            say "Then restart your shell or run: source ~/.bashrc"
            ;;
    esac
}

print_success() {
    say ""
    say "Installation complete!"
    say ""
    say "Get started:"
    say "    mc --help"
    say ""
    say "To upgrade MC CLI in the future:"
    say "    mc-update upgrade"
    say ""
}

ensure_uv
install_mc
check_path
print_success

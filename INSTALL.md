# Installation Instructions

## Prerequisites

- Python 3.8 or higher
- `~/bin` directory in your PATH

## Installation

1. Clone the repository:
```bash
git clone https://github.com/squird/mc.git
cd mc
```

2. Run the installation script:
```bash
./install.sh
```

3. Ensure `~/bin` is in your PATH (add to `~/.zshrc` or `~/.bashrc`):
```bash
export PATH="$HOME/bin:$PATH"
```

4. Reload your shell or run:
```bash
source ~/.zshrc  # or ~/.bashrc
```

5. Verify installation:
```bash
mc -h
```

## What Gets Installed

- Virtual environment: `~/bin/py_env_mc-cli`
- Command symlink: `~/bin/mc`
- Package installed in editable mode from the cloned repository

## Updating

To update to the latest version:
```bash
cd /path/to/mc
git pull
~/bin/py_env_mc-cli/bin/pip install -e .
```

## Uninstallation

```bash
rm -rf ~/bin/py_env_mc-cli
rm ~/bin/mc
```

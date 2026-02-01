---
created: 2026-01-27T15:45
title: Migrate mc-cli distribution to use pipx/uv tool for portable isolated installation
area: tooling
files:
  - bin/mc:1
---

## Problem

The current mc CLI wrapper script has a hard-coded shebang line pointing to a specific user's virtual environment:

```
#!/Users/dsquirre/bin/py_env_mc-cli/bin/python3
```

This makes the script completely non-portable:
- Only works on the original developer's machine
- Only works for user `dsquirre`
- Breaks if the virtual environment is moved or recreated
- Won't work for anyone else who installs the package

While changing to `#!/usr/bin/env python3` would be portable, it would use the system Python (or whatever Python is in PATH), which defeats the goal of isolated Python environments. We don't want mc-cli to make changes to users' global Python environment.

## Solution

Migrate mc-cli distribution to use pipx or uv tool. These tools are designed specifically for installing Python CLI applications in isolated environments:

- Users install with: `pipx install mc-cli` or `uv tool install mc-cli`
- Creates isolated venv automatically
- Puts portable wrapper in PATH
- Clean user experience
- No hard-coded paths

This is the recommended modern approach for distributing Python CLI tools with dependency isolation.

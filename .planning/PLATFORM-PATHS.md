# Platform-Specific Paths Reference

MC CLI uses platformdirs for cross-platform compatibility. File locations differ by OS.

## Configuration Files

| File | macOS | Linux (Fedora/RHEL) |
|------|-------|---------------------|
| Main config | `~/Library/Application Support/mc/config.toml` | `~/.config/mc/config.toml` |
| Container bashrc | `~/Library/Application Support/mc/bashrc/` | `~/.config/mc/bashrc/` |

## Data Files

| File | macOS | Linux (Fedora/RHEL) |
|------|-------|---------------------|
| Container state DB | `~/Library/Application Support/mc/containers.db` | `~/.local/share/mc/containers.db` |

## Cache Files

| File | macOS | Linux (Fedora/RHEL) |
|------|-------|---------------------|
| Case metadata cache | `~/Library/Caches/mc/case_metadata.db` | `~/.cache/mc/case_metadata.db` |
| API tokens | `~/.mc/token` | `~/.mc/token` |

## Workspaces

| Type | macOS | Linux (Fedora/RHEL) |
|------|-------|-------------------|
| Default base | Configured in config.toml | Configured in config.toml |
| Example path | `/Users/username/mc/<customer>/<case_number>` | `/home/username/mc/<customer>/<case_number>` |

## Implementation Notes

- **Config directory**: Uses `platformdirs.user_config_dir("mc", appauthor=False)`
- **Data directory**: Uses `platformdirs.user_data_dir("mc", "redhat")`
- **Cache directory**: Uses `platformdirs.user_cache_dir("mc", "redhat")`
- **Token file**: Legacy location at `~/.mc/token` (predates platformdirs migration)

## Verifying Paths

```bash
# Check actual paths on your system
python3 -c "
from platformdirs import user_config_dir, user_data_dir, user_cache_dir
print(f'Config: {user_config_dir(\"mc\", appauthor=False)}/config.toml')
print(f'Data:   {user_data_dir(\"mc\", \"redhat\")}/containers.db')
print(f'Cache:  {user_cache_dir(\"mc\", \"redhat\")}/case_metadata.db')
"
```

## UAT Testing

When running the UAT test plan on different platforms:

1. **macOS testers**: Use paths as shown in test plan
2. **Linux testers**: Uncomment Linux paths, comment out macOS paths in shell variables

Example from Test 3.2:
```bash
# macOS:
CACHE_DB=~/Library/Caches/mc/case_metadata.db
# Linux:
# CACHE_DB=~/.cache/mc/case_metadata.db
```

## Future Platforms

If Windows support is added:
- Config: `C:\Users\<username>\AppData\Local\mc\config.toml`
- Data: `C:\Users\<username>\AppData\Local\mc\redhat\containers.db`
- Cache: `C:\Users\<username>\AppData\Local\mc\redhat\Cache\case_metadata.db`

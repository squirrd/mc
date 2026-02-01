# Platform-Specific Paths Reference

MC CLI v2.0.1+ uses a consolidated directory structure under `~/mc/` for all platforms.

## Consolidated Directory Structure (v2.0.1+)

All MC-related files are now organized under a single `~/mc/` directory:

```
~/mc/
├── config/
│   ├── config.toml          # TOML configuration
│   └── cache/
│       └── case_metadata.db # Case metadata cache (SQLite)
├── state/
│   └── containers.db        # Container state database (SQLite)
└── cases/
    └── <customer>/
        └── <case>/          # Case workspaces
```

## File Locations (All Platforms)

| File | Path (macOS, Linux, all platforms) |
|------|-----------------------------------|
| Main config | `~/mc/config/config.toml` |
| Container state DB | `~/mc/state/containers.db` |
| Case metadata cache | `~/mc/config/cache/case_metadata.db` |
| Case workspaces | `~/mc/cases/<customer>/<case>/` |

## Auto-Migration from Legacy Paths

When you first run MC v2.0.1+, files are automatically migrated from old platformdirs locations:

### macOS Legacy → New
- `~/Library/Application Support/mc/config.toml` → `~/mc/config/config.toml`
- `~/Library/Application Support/mc/containers.db` → `~/mc/state/containers.db`
- `~/mc/cache/case_metadata.db` → `~/mc/config/cache/case_metadata.db`

### Linux Legacy → New
- `~/.config/mc/config.toml` → `~/mc/config/config.toml`
- `~/.local/share/mc/containers.db` → `~/mc/state/containers.db`
- `~/mc/cache/case_metadata.db` → `~/mc/config/cache/case_metadata.db`

Migration happens automatically on first access to each component. Original files are left in place (safe to delete after verifying migration worked).

## Benefits of Consolidated Structure

1. **Single backup location**: Just backup `~/mc/` to preserve everything
2. **Easier troubleshooting**: All MC data in one discoverable location
3. **Cross-platform consistency**: Same paths on macOS, Linux, and future platforms
4. **Simpler documentation**: No platform-specific path tables needed

## Verifying Paths

```bash
# Check that new structure exists
ls -la ~/mc/
ls -la ~/mc/config/
ls -la ~/mc/state/

# Verify config file location
cat ~/mc/config/config.toml

# Check container state database
ls -la ~/mc/state/containers.db

# Check cache
ls -la ~/mc/config/cache/case_metadata.db
```

## Container Image

The MC CLI container image must be built before using container features.

### Building the Image

**Option 1: Direct command (from project root)**
```bash
podman build -t mc-rhel10:latest -f container/Containerfile .
```

**Option 2: Using build script (from anywhere)**
```bash
./container/build.sh
```

The script automatically:
- Navigates to project root
- Builds image with correct name (`mc-rhel10:latest`)
- Uses correct Containerfile path (`container/Containerfile`)

### Verifying the Build

```bash
# Check image exists
podman images | grep mc-rhel10

# Should show:
# mc-rhel10    latest    <image-id>    <timestamp>    549 MB
```

## Implementation Notes

- **Consolidated paths**: v2.0.1+ no longer uses platformdirs for config/state/cache
- **Backward compatibility**: Auto-migration from old platformdirs locations
- **Legacy auth tokens**: `~/.mc/token` deprecated (use `~/mc/config/config.toml` instead)
- **Platform consistency**: All platforms use `~/mc/` structure

## Future Platforms

If Windows support is added, the same structure will be used:
```
C:\Users\<username>\mc\
├── config\
│   ├── config.toml
│   └── cache\
│       └── case_metadata.db
├── state\
│   └── containers.db
└── cases\
    └── <customer>\
        └── <case>\
```

---
*Last updated: 2026-02-02 (v2.0.1 directory consolidation)*

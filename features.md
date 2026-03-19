# MC CLI — Feature Reference

**Current Version:** v2.0.6 | **Python:** 3.11+ | **Package Manager:** uv

---

## `mc` — MC CLI Tool

### Global Flags

| Flag | Description |
|------|-------------|
| `--version` | Show installed version (suppresses update banner) |
| `--debug` | Enable debug logging |
| `--json-logs` | Output logs as JSON (for CI/automation) |
| `--debug-file <path>` | Write debug logs to a file |

---

### Commands

#### `mc <case_number>` — Quick Access (shorthand)
Shorthand for `mc case <number>`. Detects an 8-digit argument and routes directly to the terminal attachment workflow. Same behavior as `mc case`.

---

#### `mc case <case_number>` — Attach Terminal to Case Container
Launches a new iTerm2 or Terminal.app window attached to the case's container.
- Auto-creates container if it doesn't exist
- Auto-starts container if stopped
- Authenticates with Red Hat API to pull case metadata
- Uses iTerm2 Python API with **MC-Term** profile (hides raw `podman exec` from scrollback)
- Falls back to Terminal.app if iTerm2 API unavailable (shows once-per-day fallback notice)
- Tracks window ID in SQLite registry — re-running focuses the existing window instead of creating a duplicate
- Creates a new window if the tracked window was manually closed

---

#### `mc create <case_number>` — Create Workspace
Creates the workspace directory structure for a case using Red Hat API metadata.
- `-d` / `--download` — also download all attachments after workspace creation
- Uses cached case metadata (5-minute TTL) when available

---

#### `mc attach <case_number>` — Download Attachments
Downloads all attachments for a case to the workspace.
- **Default:** parallel download (8 concurrent threads) with Rich progress bars
- `--serial` — download one at a time (for debugging)
- `--quiet` — suppress progress output (errors only)
- Skips files that already exist
- Warns on files > 3GB
- Shows per-file speed/ETA during download

---

#### `mc check <case_number>` — Check Workspace Status
Validates the workspace file structure for a case.
- `-f` / `--fix` — automatically create any missing files (runs create if status is WARN)
- Reports WARN (fixable missing files) or FATAL (structural issues)

---

#### `mc case-comments <case_number>` — Display Case Comments
Fetches and displays comments from a Salesforce case via Red Hat API.
- Uses cached case metadata when available

---

#### `mc go <case_number>` — Open Salesforce Case
Opens the Salesforce case in Google Chrome.
- `-l` / `--link` — print the URL instead of launching the browser

---

#### `mc ls <uid>` — LDAP Directory Search
Searches for a Red Hat employee by UID in LDAP.
- `-A` / `--all` — show raw full LDAP output

---

#### `mc version` — Show Version & Check for Updates
Displays the installed version.
- `--update` — force an immediate version check against GitHub (bypasses the hourly throttle)

---

#### `mc container` — Container Lifecycle Management
Sub-commands for direct container operations (no Red Hat API auth required).

| Sub-command | Description |
|-------------|-------------|
| `mc container list` | List all containers in a formatted table (case, status, customer, description, created) |
| `mc container create <case_number>` | Create a container and workspace for a case |
| `mc container stop <case_number...>` | Stop one or more containers (supports multiple case numbers) |
| `mc container delete <case_number...>` | Delete one or more containers (preserves workspace files) |
| `mc container exec <case_number> <command...>` | Execute a command inside a container and return output |
| `mc container reconcile` | Validate window registry, remove stale entries for closed terminal windows |

---

### Background / Automatic Behaviors

| Feature | Description |
|---------|-------------|
| **Update banner** | Rich Panel on stderr at startup when a newer version is available; shown at most once per calendar day; suppressed for `--version` and piped runs |
| **Pin-aware banner** | If a version is pinned, banner message includes unpin instructions |
| **Auto-config wizard** | Runs setup wizard on first launch when no config file exists |
| **Cache (5-min TTL)** | Case metadata from Red Hat API is cached in SQLite to reduce repeated API calls |
| **Token caching** | OAuth access tokens cached with expiration tracking to avoid redundant auth requests |
| **Window registry cleanup** | Stale window entries are automatically cleaned up on startup |
| **Runtime mode guard** | In agent (container) mode, version checks and auto-updates are disabled |
| **State migration** | Automatically migrates container DB and config from old platformdirs locations to `~/mc/` |

---

## `mc-update` — Standalone Update Tool

**Entry point:** `mc-update` (independent from `mc` CLI — survives partial package upgrades)

### Commands

| Command | Description |
|---------|-------------|
| `mc-update upgrade` | Runs `uv tool upgrade mc` with live streaming output. Verifies the upgrade by running `mc --version`. Prints recovery instructions (`uv tool install --force mc`) on failure. Blocked when a version pin is active. |
| `mc-update pin <version>` | Pins MC CLI to a specific version (e.g. `2.0.3` or `v2.0.3`). Validates version format, checks GitHub releases API to confirm the version exists, then persists to `config.toml`. |
| `mc-update unpin` | Removes the active version pin, restoring latest-tracking behavior. |
| `mc-update check` | Displays a version status table: installed version, latest available, active pin, and update availability. |

### Constraints & Guards
- All pin/unpin/check commands are **blocked in agent mode** (inside a container) — use host machine only
- `upgrade` is **blocked when a pin is active** — must `unpin` first
- GitHub validation uses the releases API with proper headers and 10s timeout
- Survives partial package replacement because it has no dependency on `mc.cli.main`

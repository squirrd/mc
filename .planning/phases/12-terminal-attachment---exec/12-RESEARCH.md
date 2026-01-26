# Phase 12: Terminal Attachment & Exec - Research

**Researched:** 2026-01-26
**Domain:** Terminal automation, container attachment, TTY handling
**Confidence:** HIGH

## Summary

This phase requires programmatically launching new terminal windows that attach to running Podman containers with interactive shells. The standard approach combines platform-specific terminal automation (AppleScript for macOS, command-line arguments for Linux terminal emulators) with Podman's `exec -it` command for TTY attachment. Critical components include TTY detection to prevent breaking piped output, terminal emulator detection via environment variables, and shell customization through `--env` flag injection.

**Key challenges:**
- Each terminal emulator (iTerm2, Terminal.app, gnome-terminal, konsole, xfce4-terminal) has different command syntax
- Preventing multiple simultaneous terminal attachments requires label-based container tracking
- Terminal window titles use ANSI escape sequences that vary by platform
- Shell customization must handle both interactive and non-interactive contexts

**Primary recommendation:** Use `podman exec -it --env BASH_ENV=/path/to/custom.bashrc` for shell attachment, AppleScript `osascript` for macOS terminal launching, and native command-line flags for Linux terminal emulators. Detect terminals via `$TERM_PROGRAM` and `$ITERM_SESSION_ID` environment variables, and use `github.com/mattn/go-isatty` for TTY detection.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| github.com/mattn/go-isatty | Latest | TTY detection in Go | Most popular Go library for detecting interactive terminals, cross-platform |
| podman exec | Latest | Container command execution | Official Podman method for executing commands in running containers |
| osascript | Built-in macOS | AppleScript execution | Native macOS tool for terminal automation, no dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| github.com/kirsle/configdir | Latest | Cross-platform config directories | Storing MC config files in OS-appropriate locations |
| github.com/mitchellh/go-homedir | Latest | Home directory detection | Cross-platform home directory path resolution |
| os/exec | stdlib | Running external commands | Launching osascript, terminal emulators, all external processes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AppleScript (macOS) | ttab utility | ttab is third-party dependency, requires installation; AppleScript is built-in |
| podman exec | podman attach | attach only connects to main container process, can't inject custom shell; exec starts new process with custom environment |
| Environment variables for shell config | --rcfile flag | BASH_ENV works for non-interactive shells too; --rcfile only for interactive |

**Installation:**
```bash
go get github.com/mattn/go-isatty
go get github.com/kirsle/configdir
go get github.com/mitchellh/go-homedir
```

## Architecture Patterns

### Recommended Project Structure
```
cmd/mc/
├── terminal/           # Terminal launcher abstraction
│   ├── launcher.go     # Interface and platform detection
│   ├── macos.go        # iTerm2, Terminal.app launchers
│   └── linux.go        # gnome-terminal, konsole, xfce4-terminal
├── container/          # Container management (from Phase 11)
│   └── exec.go         # Container attachment logic
└── shell/              # Shell customization
    ├── bashrc.go       # Custom bashrc generation
    └── banner.go       # Welcome banner generation
```

### Pattern 1: Platform-Specific Terminal Launching
**What:** Abstract terminal launching behind interface, use build tags or runtime detection for platform-specific implementations
**When to use:** When supporting multiple terminal emulators across macOS and Linux

**Example:**
```go
// Source: Research synthesis from multiple sources
type TerminalLauncher interface {
    Launch(ctx context.Context, opts LaunchOptions) error
    Detect() ([]string, error) // Returns available terminal emulators
}

type LaunchOptions struct {
    Title       string
    Command     string
    WorkDir     string
    AutoFocus   bool
}

// macOS implementation
type MacOSLauncher struct {
    emulator string // "iTerm2" or "Terminal.app"
}

func (m *MacOSLauncher) Launch(ctx context.Context, opts LaunchOptions) error {
    script := m.buildAppleScript(opts)
    cmd := exec.CommandContext(ctx, "osascript", "-e", script)
    return cmd.Start() // Non-blocking
}

// Linux implementation
type LinuxLauncher struct {
    emulator string // "gnome-terminal", "konsole", etc.
}

func (l *LinuxLauncher) Launch(ctx context.Context, opts LaunchOptions) error {
    args := l.buildArgs(opts)
    cmd := exec.CommandContext(ctx, l.emulator, args...)
    return cmd.Start() // Non-blocking
}
```

### Pattern 2: Container Attachment with Custom Environment
**What:** Use `podman exec -it` with environment variable injection for shell customization
**When to use:** When attaching to containers and needing custom shell configuration

**Example:**
```go
// Source: https://docs.podman.io/en/latest/markdown/podman-exec.1.html
func AttachToContainer(containerID, bashrcPath string) error {
    cmd := exec.Command("podman", "exec",
        "-it",                                    // Interactive TTY
        "--env", "BASH_ENV="+bashrcPath,         // Custom bashrc
        "--env", "PS1=[MC-"+caseNumber+"] \\w$ ", // Custom prompt
        containerID,
        "/bin/bash",
    )

    cmd.Stdin = os.Stdin
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    return cmd.Run() // Blocking - waits for shell exit
}
```

### Pattern 3: TTY Detection for Graceful Degradation
**What:** Detect if running in interactive terminal vs pipe/script, prevent terminal launch when inappropriate
**When to use:** Every invocation of `mc case <number>` command

**Example:**
```go
// Source: https://github.com/mattn/go-isatty
import "github.com/mattn/go-isatty"

func ShouldLaunchTerminal() bool {
    // Only launch terminal if stdout is a TTY
    // If piped or redirected, this returns false
    return isatty.IsTerminal(os.Stdout.Fd()) ||
           isatty.IsCygwinTerminal(os.Stdout.Fd())
}
```

### Pattern 4: Terminal Emulator Detection
**What:** Detect which terminal emulator is running via environment variables
**When to use:** Auto-detecting user's terminal for seamless experience

**Example:**
```go
// Source: Research synthesis from terminal detection patterns
func DetectTerminalEmulator() string {
    // iTerm2 detection
    if os.Getenv("TERM_PROGRAM") == "iTerm.app" {
        return "iTerm2"
    }
    if os.Getenv("ITERM_SESSION_ID") != "" {
        return "iTerm2"
    }

    // Terminal.app detection
    if os.Getenv("TERM_PROGRAM") == "Apple_Terminal" {
        return "Terminal.app"
    }

    // Konsole detection
    if os.Getenv("KONSOLE_DBUS_SERVICE") != "" ||
       os.Getenv("KONSOLE_DBUS_SESSION") != "" {
        return "konsole"
    }

    // XFCE Terminal detection
    if os.Getenv("COLORTERM") == "xfce4-terminal" {
        return "xfce4-terminal"
    }

    return "unknown"
}
```

### Pattern 5: Label-Based Container Tracking
**What:** Use Podman labels to track which containers have attached terminals
**When to use:** Preventing multiple terminal sessions to same container

**Example:**
```go
// Source: https://docs.podman.io/en/latest/markdown/podman-run.1.html
// Set label at container creation
func CreateContainer(caseID string) error {
    cmd := exec.Command("podman", "create",
        "--label", "mc.case.id="+caseID,
        "--label", "mc.terminal.attached=false", // Initially no terminal
        "--name", "mc-"+caseID,
        containerImage,
    )
    return cmd.Run()
}

// Check if terminal already attached
func IsTerminalAttached(caseID string) (bool, error) {
    cmd := exec.Command("podman", "inspect",
        "--format", "{{.Config.Labels}}",
        "mc-"+caseID,
    )
    output, err := cmd.Output()
    if err != nil {
        return false, err
    }

    // Parse labels and check mc.terminal.attached
    return strings.Contains(string(output), "mc.terminal.attached:true"), nil
}

// Update label when attaching terminal
func MarkTerminalAttached(caseID string, attached bool) error {
    // Note: Labels can't be updated on running containers
    // Instead, track in separate metadata store or use container annotations
    // Alternative: Query active podman exec sessions
}
```

### Pattern 6: Window Title Setting with ANSI Escape Sequences
**What:** Set terminal window titles using OSC escape sequences
**When to use:** After launching terminal, before displaying prompt

**Example:**
```go
// Source: https://alvinalexander.com/mac-os-x/how-set-mac-osx-terminal-title-titlebar-echo/
// Source: ANSI escape code documentation
func SetTerminalTitle(title string) {
    // OSC 0 ; <title> BEL
    // \033]0; is the escape sequence
    // \007 is the bell character (BEL)
    fmt.Printf("\033]0;%s\007", title)
}

// Use in welcome banner
func PrintWelcomeBanner(caseID, customer, description string) {
    title := fmt.Sprintf("%s - %s - %s", caseID, customer, description)
    SetTerminalTitle(title)

    fmt.Println("=================================================")
    fmt.Printf("Case: %s\n", caseID)
    fmt.Printf("Customer: %s\n", customer)
    fmt.Printf("Description: %s\n", description)
    fmt.Println("=================================================")
}
```

### Anti-Patterns to Avoid

- **Using podman attach instead of exec:** `podman attach` connects to the main container process (PID 1), which doesn't allow injecting custom shell environment. Use `podman exec` to start a new shell with custom configuration.

- **Blocking on terminal launch:** When launching a new terminal window, use `cmd.Start()` not `cmd.Run()` so the original terminal returns to prompt immediately. The new terminal runs independently.

- **Assuming single terminal type per platform:** Linux has multiple desktop environments (GNOME, KDE, XFCE) with different default terminals. Detect and support multiple options, not just one per OS.

- **Using --rcfile for shell customization:** The `--rcfile` flag doesn't work with `podman exec` because you can't pass flags to the shell. Use `BASH_ENV` environment variable instead.

- **Setting container labels to track state:** Podman doesn't allow updating labels on running containers. Use alternative methods like querying active `podman exec` sessions or maintaining external state.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TTY detection | Custom syscall wrappers | github.com/mattn/go-isatty | Handles platform differences (Linux, macOS, Windows), Cygwin terminals, tested edge cases |
| Cross-platform config paths | Hard-coded ~/.mc paths | github.com/kirsle/configdir | Respects XDG Base Directory Spec on Linux, uses proper locations on macOS/Windows |
| Home directory detection | os.Getenv("HOME") | github.com/mitchellh/go-homedir | Works in cross-compilation, handles Windows %USERPROFILE%, supports ~ expansion |
| Terminal launching library | Custom abstraction | Individual platform tools | Each terminal emulator has unique syntax; thin wrappers better than heavy abstraction |
| AppleScript generation | String concatenation | Structured approach with escaping | AppleScript strings need proper escaping for quotes, newlines, special characters |

**Key insight:** Terminal automation is highly platform-specific with little standardization. Use platform-native tools (osascript, terminal emulator CLIs) rather than trying to abstract away differences. Focus abstraction at the business logic level (LaunchTerminal interface), not the implementation level.

## Common Pitfalls

### Pitfall 1: Terminal Closes Immediately After Launch
**What goes wrong:** Terminal window opens and closes instantly when running `podman exec -it`
**Why it happens:** The command is run in the terminal launcher's context (e.g., AppleScript), and when the launcher process exits, the terminal sees EOF on stdin and closes
**How to avoid:**
- For AppleScript (iTerm2/Terminal.app): Use `write text` command which sends input to the shell, not `do script` with direct command execution
- For Linux terminals: The terminal emulator spawns shell as child process, so it stays open naturally
**Warning signs:** Terminal flashes briefly then disappears, no error message visible

### Pitfall 2: Using -t Flag When Piping/Redirecting
**What goes wrong:** When using `podman exec -it` in non-TTY context (pipes, redirection), it fails with "cannot allocate pseudo-TTY" error or hangs
**Why it happens:** The `-t` (TTY) flag requires an actual terminal, fails when stdout is redirected or piped
**How to avoid:** Always check `isatty.IsTerminal()` before using `-t` flag; for scripts/automation use `-i` only
**Warning signs:** Error messages about "not a tty" or "inappropriate ioctl for device"
**Example:**
```go
// WRONG: Always uses -it
exec.Command("podman", "exec", "-it", containerID, "bash")

// RIGHT: Conditional TTY allocation
flags := []string{"exec", "-i"}
if isatty.IsTerminal(os.Stdout.Fd()) {
    flags = append(flags, "-t")
}
cmd := exec.Command("podman", append(flags, containerID, "bash")...)
```

### Pitfall 3: Race Condition on Container Startup
**What goes wrong:** Launching terminal immediately after `podman create` or `podman start` fails because container isn't ready
**Why it happens:** Container creation/startup is asynchronous; trying to `exec` before the container is running returns "container state improper"
**How to avoid:**
- Use `podman start --attach` to wait for startup
- Poll `podman inspect --format '{{.State.Status}}'` until status is "running"
- Add small delay (100-200ms) after start before exec
**Warning signs:** Intermittent failures, errors like "container not running" despite just starting it

### Pitfall 4: BASH_ENV Not Executed
**What goes wrong:** Custom bashrc set via `BASH_ENV` environment variable doesn't execute, shell has default config
**Why it happens:**
- Path to bashrc is wrong (relative path instead of absolute)
- File doesn't exist in container filesystem
- File has wrong permissions (not readable)
- BASH_ENV only works for non-interactive shells in some contexts
**How to avoid:**
- Always use absolute paths for BASH_ENV
- Copy/mount bashrc into container before exec
- Verify file exists: `podman exec containerID test -f /path/to/bashrc`
- Use both BASH_ENV and --env PS1 for redundancy
**Warning signs:** Custom prompt doesn't appear, aliases/functions not defined

### Pitfall 5: Terminal Detection Fails in tmux/screen
**What goes wrong:** `$TERM_PROGRAM` shows "tmux" instead of "iTerm.app" when user is in tmux session
**Why it happens:** tmux/screen overrides terminal environment variables to ensure compatibility
**How to avoid:**
- Check multiple environment variables: TERM_PROGRAM, ITERM_SESSION_ID, LC_TERMINAL, __CFBundleIdentifier
- Fall back to user configuration if auto-detection unreliable
- Document that terminal detection works best outside tmux/screen
**Warning signs:** Auto-detection works sometimes but not in tmux, user reports wrong terminal launched

### Pitfall 6: AppleScript Injection Vulnerabilities
**What goes wrong:** Case descriptions with quotes or special characters break AppleScript syntax, cause errors or command injection
**Why it happens:** AppleScript string interpolation without escaping allows malicious input to break out of quotes
**How to avoid:**
- Escape all user input in AppleScript strings (backslash escape quotes and backslashes)
- Use parameterized approaches where possible
- Validate/sanitize case metadata from Salesforce
**Warning signs:** AppleScript syntax errors when case has quotes in description, potential for arbitrary command execution
**Example:**
```go
// WRONG: Direct string interpolation
script := fmt.Sprintf(`tell application "iTerm2"
    set newWindow to (create window with default profile)
    tell current session of newWindow
        write text "echo %s"
    end tell
end tell`, caseDescription) // VULNERABLE

// RIGHT: Escape special characters
func escapeAppleScript(s string) string {
    s = strings.ReplaceAll(s, "\\", "\\\\")
    s = strings.ReplaceAll(s, "\"", "\\\"")
    return s
}
script := fmt.Sprintf(`...write text "echo %s"...`, escapeAppleScript(caseDescription))
```

### Pitfall 7: Window Focus Issues on macOS
**What goes wrong:** New terminal window opens but doesn't come to foreground, stays hidden behind other windows
**Why it happens:** macOS window management requires explicit activation; creating window doesn't auto-focus
**How to avoid:**
- For iTerm2: Use `activate application "iTerm2"` in AppleScript
- For Terminal.app: Call `activate` before creating window
**Warning signs:** Terminal opens but user doesn't see it, appears in background
**Example:**
```applescript
tell application "iTerm2"
    activate  # Brings iTerm2 to foreground
    set newWindow to (create window with default profile)
    # ...
end tell
```

### Pitfall 8: Container Label Limitations
**What goes wrong:** Attempting to update container labels to track terminal attachment fails
**Why it happens:** Podman doesn't support updating labels on existing containers (neither stopped nor running)
**How to avoid:**
- Don't use labels for runtime state tracking
- Alternative 1: Query active `podman exec` sessions via `podman ps` filters
- Alternative 2: Maintain external state file/database
- Alternative 3: Use container annotations (if supported for runtime updates)
**Warning signs:** `podman label` commands fail, labels don't change after creation

### Pitfall 9: Terminal Emulator Not Installed
**What goes wrong:** Code tries to launch gnome-terminal but user has KDE/XFCE desktop, terminal not available
**Why it happens:** Assuming desktop environment based on OS, not checking if terminal binary exists
**How to avoid:**
- Check multiple terminal options in priority order
- Use `exec.LookPath("terminal-name")` to verify binary exists
- Provide clear error message with installation instructions if no terminal found
- Let user configure preferred terminal in MC config
**Warning signs:** `exec` errors "terminal-name: command not found"
**Example:**
```go
func findAvailableTerminal() (string, error) {
    terminals := []string{"gnome-terminal", "konsole", "xfce4-terminal", "xterm"}
    for _, term := range terminals {
        if _, err := exec.LookPath(term); err == nil {
            return term, nil
        }
    }
    return "", errors.New("no supported terminal emulator found. Install one of: " +
                          strings.Join(terminals, ", "))
}
```

### Pitfall 10: Detach Keys Confusion
**What goes wrong:** User presses Ctrl+D to exit container but container stays running with orphaned process
**Why it happens:** Confusing `podman attach` detach keys (Ctrl+P, Ctrl+Q) with normal shell exit (Ctrl+D or `exit`)
**How to avoid:**
- Use `podman exec` not `podman attach` (exec process exits cleanly with shell)
- Document that `exit` or Ctrl+D exits the shell
- Disable detach keys in exec context (not needed, can confuse users)
**Warning signs:** User complaints about "can't exit container", multiple bash processes accumulating

## Code Examples

Verified patterns from official sources:

### Terminal Launch - macOS iTerm2
```applescript
-- Source: https://iterm2.com/documentation-scripting.html
-- Source: Research synthesis from multiple AppleScript examples
tell application "iTerm2"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow
        set name to "12345678 - CustomerName - Description"
        write text "podman exec -it mc-12345678 /bin/bash"
    end tell
end tell
```

### Terminal Launch - macOS Terminal.app
```applescript
-- Source: Research synthesis from AppleScript patterns
tell application "Terminal"
    activate
    set newTab to do script "podman exec -it mc-12345678 /bin/bash"
    set custom title of newTab to "12345678 - CustomerName - Description"
end tell
```

### Terminal Launch - Linux gnome-terminal
```bash
# Source: https://linuxcommandlibrary.com/man/gnome-terminal
gnome-terminal \
    --title="12345678 - CustomerName - Description" \
    -- bash -c "podman exec -it mc-12345678 /bin/bash"
```

### Terminal Launch - Linux konsole
```bash
# Source: https://linuxcommandlibrary.com/man/konsole
konsole \
    --noclose \
    -e podman exec -it mc-12345678 /bin/bash
# Note: Title set via escape sequences after launch, not command-line flag
```

### Terminal Launch - Linux xfce4-terminal
```bash
# Source: https://docs.xfce.org/apps/xfce4-terminal/command-line
xfce4-terminal \
    --title="12345678 - CustomerName - Description" \
    --command="podman exec -it mc-12345678 /bin/bash"
```

### Podman Exec with Custom Shell Environment
```go
// Source: https://docs.podman.io/en/latest/markdown/podman-exec.1.html
import "os/exec"

func launchContainerShell(containerID, customBashrc string) error {
    cmd := exec.Command("podman", "exec",
        "--interactive",
        "--tty",
        "--env", "BASH_ENV="+customBashrc,
        "--env", "PS1=[MC-"+containerID+"] \\w\\$ ",
        "--workdir", "/workspace",
        containerID,
        "/bin/bash",
    )

    // Connect to current terminal's stdin/stdout/stderr
    cmd.Stdin = os.Stdin
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    return cmd.Run() // Blocking until shell exits
}
```

### Custom bashrc for Container
```bash
# Source: Bash initialization best practices
# /path/to/mc-custom.bashrc

# Set custom prompt (redundant with --env PS1, but ensures it's set)
export PS1='[MC-\${MC_CASE_ID}] \w\$ '

# Helper aliases
alias ll='ls -lah'
alias case-info='echo "Case: ${MC_CASE_ID}"'

# Helper functions
mc-help() {
    echo "MC Container Environment"
    echo "  exit         - Exit container and close terminal"
    echo "  case-info    - Show current case information"
}

# Display welcome banner with case metadata
if [ -n "$MC_CASE_ID" ]; then
    echo "================================================="
    echo "Case: ${MC_CASE_ID}"
    echo "Customer: ${MC_CUSTOMER}"
    echo "Description: ${MC_DESCRIPTION}"
    echo "================================================="
fi
```

### TTY Detection
```go
// Source: https://github.com/mattn/go-isatty
import (
    "os"
    "github.com/mattn/go-isatty"
)

func shouldLaunchTerminal() bool {
    // Check if stdout is a terminal
    if !isatty.IsTerminal(os.Stdout.Fd()) {
        // Also check for Cygwin terminal (Windows)
        if !isatty.IsCygwinTerminal(os.Stdout.Fd()) {
            return false
        }
    }
    return true
}

func main() {
    if !shouldLaunchTerminal() {
        fmt.Fprintln(os.Stderr, "Error: mc case command requires interactive terminal")
        fmt.Fprintln(os.Stderr, "This command cannot be used in pipes or scripts")
        os.Exit(1)
    }

    // Proceed with terminal launch...
}
```

### Container Label Querying
```bash
# Source: https://docs.podman.io/en/latest/markdown/podman-ps.1.html
# Query containers by label
podman ps --filter label=mc.case.id=12345678 --format '{{.ID}}'

# Inspect container labels
podman inspect --format '{{.Config.Labels}}' mc-12345678

# Inspect specific label value
podman inspect --format '{{index .Config.Labels "mc.case.id"}}' mc-12345678
```

### Non-Blocking Terminal Launch
```go
// Source: Go os/exec documentation
import "os/exec"

func launchTerminalNonBlocking(script string) error {
    cmd := exec.Command("osascript", "-e", script)

    // Start() returns immediately, doesn't wait for completion
    if err := cmd.Start(); err != nil {
        return fmt.Errorf("failed to launch terminal: %w", err)
    }

    // Optionally, clean up process in background
    go func() {
        cmd.Wait() // Reap zombie process
    }()

    return nil
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| podman attach | podman exec -it | Always available | exec allows custom environment, multiple sessions; attach limited to main process |
| Docker compatibility | Podman-native features | Podman 1.0+ (2019) | Can use Podman-specific labels, annotations without Docker compatibility concerns |
| Manual container lifecycle | Auto-create on access | Pattern emerging 2024+ | Better UX: `mc case 12345` creates/starts/attaches in one step |
| Static terminal detection | Multi-stage detection with fallbacks | 2023+ | More robust across desktop environments, tmux sessions |
| --rcfile for shell config | BASH_ENV environment variable | Long-standing | BASH_ENV more reliable in exec context, works for non-interactive too |
| AppleScript for iTerm2 | Python API | iTerm2 3.0+ (2017) | AppleScript still supported but Python API preferred for complex automation; simple AppleScript fine for basic launch |

**Deprecated/outdated:**
- **ttab utility for macOS terminal launching:** While convenient, it's a third-party dependency. Direct AppleScript is more portable and equally simple for our use case.
- **Docker-specific assumptions:** Many tutorials assume Docker commands (`docker exec`), but Podman has minor syntax differences and additional features (labels, pods). Always verify with Podman docs.
- **$TERM for terminal detection:** The `$TERM` variable (e.g., "xterm-256color") indicates terminal capabilities, not which terminal emulator is running. Use `$TERM_PROGRAM` instead.

## Open Questions

Things that couldn't be fully resolved:

1. **Detecting already-attached terminals**
   - What we know: Container labels can't be updated at runtime; need alternative approach
   - What's unclear: Best method to track active exec sessions (query podman, external state, or accept multiple terminals?)
   - Recommendation: Start with querying `podman exec` process list, fall back to warning message if detection unreliable; CONTEXT.md indicates error if already attached, but implementation may need to be "best effort"

2. **Terminal.app vs iTerm2 priority on macOS**
   - What we know: Both are common; iTerm2 more popular among developers; detection works for both
   - What's unclear: Which to prefer when both installed?
   - Recommendation: Check user config first, then prefer iTerm2 (better AppleScript support, more features), fall back to Terminal.app

3. **RHEL/Fedora default terminals**
   - What we know: RHEL 8+ uses GNOME (gnome-terminal) exclusively; Fedora Workstation uses GNOME by default
   - What's unclear: Whether Fedora spins (KDE, XFCE) are common enough to prioritize
   - Recommendation: Support gnome-terminal (RHEL/Fedora Workstation), konsole (Fedora KDE spin), xfce4-terminal (Fedora XFCE spin), in that priority order

4. **Window geometry/size**
   - What we know: CONTEXT.md specifies "default size/geometry (not configurable)"
   - What's unclear: Should we explicitly set a size, or truly accept terminal's default?
   - Recommendation: Don't specify geometry flags; let terminal use its configured defaults; simpler and respects user preferences

5. **Shell exit behavior (terminal auto-close)**
   - What we know: CONTEXT.md says "terminal closes when user exits container"; some terminals do this by default, others don't
   - What's unclear: Whether to configure terminal to auto-close, or rely on defaults
   - Recommendation:
     - macOS: iTerm2 and Terminal.app close automatically when shell exits (default behavior)
     - Linux: gnome-terminal, konsole, xfce4-terminal stay open by default
     - Action: Document difference; consider it acceptable variance (Linux users can close manually)

## Sources

### Primary (HIGH confidence)
- [Podman exec documentation](https://docs.podman.io/en/latest/markdown/podman-exec.1.html) - Command flags, TTY allocation, environment variables
- [Podman attach documentation](https://docs.podman.io/en/latest/markdown/podman-attach.1.html) - Attach vs exec differences, detach keys
- [Podman ps documentation](https://docs.podman.io/en/latest/markdown/podman-ps.1.html) - Label filtering syntax
- [Podman run documentation](https://docs.podman.io/en/latest/markdown/podman-run.1.html) - Label syntax at creation
- [Podman inspect documentation](https://docs.podman.io/en/latest/markdown/podman-inspect.1.html) - Querying container metadata
- [iTerm2 AppleScript documentation](https://iterm2.com/documentation-scripting.html) - Window creation, command execution
- [XFCE Terminal command-line options](https://docs.xfce.org/apps/xfce4-terminal/command-line) - Window, title, command flags
- [github.com/mattn/go-isatty](https://github.com/mattn/go-isatty) - TTY detection library, cross-platform support
- [macOS Terminal title escape sequences](https://alvinalexander.com/mac-os-x/how-set-mac-osx-terminal-title-titlebar-echo/) - OSC sequences for title setting
- [ANSI Escape Codes (GitHub Gist)](https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797) - Comprehensive ANSI/OSC sequence reference

### Secondary (MEDIUM confidence)
- [ttab utility](https://github.com/mklement0/ttab) - Alternative terminal launching approach (verified but not using)
- [Konsole command-line man page](https://linuxcommandlibrary.com/man/konsole) - Verified with multiple sources
- [gnome-terminal man page](https://linuxcommandlibrary.com/man/gnome-terminal) - Verified with multiple sources
- [BASH_ENV environment variable](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html) - Official Bash documentation
- [Go os/exec package](https://pkg.go.dev/os/exec) - Standard library documentation
- [github.com/kirsle/configdir](https://github.com/kirsle/configdir) - Config directory library, XDG spec compliance
- [github.com/mitchellh/go-homedir](https://github.com/mitchellh/go-homedir) - Home directory detection library
- [Red Hat containers documentation](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/building_running_and_managing_containers/assembly_working-with-containers_building-running-and-managing-containers) - RHEL container patterns
- [RHEL desktop environment changes](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/considerations_in_adopting_rhel_8/desktop-and-graphics_considerations-in-adopting-rhel-8) - KDE removal, GNOME default

### Tertiary (LOW confidence)
- [Terminal emulator comparison 2026](https://thectoclub.com/tools/best-terminal-emulator/) - Market overview, not authoritative
- Various blog posts and Stack Overflow answers - Used for pattern validation only, verified against official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Podman documentation, established Go libraries with clear use cases
- Architecture: HIGH - Patterns verified against official documentation and common Go practices
- Pitfalls: MEDIUM-HIGH - Mix of documented issues (official sources) and common patterns (community experience)
- Linux terminal support: MEDIUM - Official docs for each terminal, but RHEL/Fedora defaults based on desktop environment docs rather than explicit terminal policy
- macOS terminal support: HIGH - Official Apple and iTerm2 documentation, AppleScript well-documented
- Already-attached detection: LOW - No official Podman API for this; need to implement custom solution

**Research date:** 2026-01-26
**Valid until:** ~30 days (stable domain: Podman, terminal emulators, bash don't change rapidly)

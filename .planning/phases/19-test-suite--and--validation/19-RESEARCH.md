# Phase 19: Test Suite & Validation - Research

**Researched:** 2026-02-08
**Domain:** Python testing with pytest, integration testing, platform-specific testing
**Confidence:** HIGH

## Summary

This phase requires comprehensive testing of the window tracking system (phases 15-18) to prove no duplicate terminals are created. Research focused on pytest integration testing patterns, platform-specific testing strategies, and test isolation techniques for systems with real external dependencies (Podman containers, terminal windows, window registries).

**Key findings:**
- Pytest 9.0+ is the standard for Python testing in 2026, with mature plugin ecosystem
- Integration tests should use real components (not mocks) for critical paths to catch real bugs
- WindowRegistry testing requires SQLite isolation strategies (in-memory or separate DB files)
- Platform-specific tests need careful skip markers and conditional execution
- Test cleanup is critical for tests that create real resources (containers, windows, registry entries)

**Primary recommendation:** Use pytest with real components (Podman, terminals, AppleScript), implement robust cleanup fixtures, and leverage pytest-cov for coverage tracking. Platform-specific tests should use `@pytest.mark.skipif` with platform detection.

## Standard Stack

The established testing stack for Python integration testing in 2026:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0+ | Test framework | Industry standard, replaced unittest for most projects due to easy syntax and strong features |
| pytest-cov | 7.0+ | Coverage measurement | Official pytest coverage plugin, integrates with coverage.py |
| pytest-mock | 3.15+ | Mocking/stubbing | Provides mocker fixture, cleaner than unittest.mock directly |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-console-scripts | 1.4+ | CLI testing | Testing entry points like `mc case XXXXX` |
| responses | 0.25+ | HTTP mocking | Mocking API calls (Salesforce, Red Hat API) |
| pytest-xdist | Latest | Parallel execution | Speed up test suite (use with caution for integration tests with shared resources) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | pytest has simpler syntax, better fixtures, more plugins (unittest is built-in but verbose) |
| pytest-cov | coverage.py directly | pytest-cov provides better pytest integration but coverage.py gives more control |
| pytest-mock | unittest.mock | pytest-mock provides fixture-based mocking which is cleaner in pytest tests |

**Installation:**
```bash
# Already in pyproject.toml dev dependencies
pip install pytest>=9.0.0 pytest-cov>=7.0.0 pytest-mock>=3.15.0 pytest-console-scripts>=1.4.0
```

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── unit/                          # Fast unit tests (mocked dependencies)
│   ├── test_window_registry.py   # WindowRegistry DB operations
│   ├── test_terminal_launcher.py # Launcher logic (mocked AppleScript)
│   └── test_*.py                 # Other unit tests
├── integration/                   # Slower integration tests (real components)
│   ├── test_case_terminal.py     # End-to-end terminal workflow
│   ├── test_duplicate_prevention.py  # Window tracking integration
│   └── conftest.py               # Shared fixtures
├── fixtures/                      # Test data
│   └── test_data/                # Sample case data
└── conftest.py                   # Root-level fixtures
```

### Pattern 1: Integration Tests with Real Components
**What:** Tests use real Podman containers, real terminal launchers, real AppleScript execution
**When to use:** Testing critical paths where mocking would hide real bugs (like iTerm2 AppleScript limitations)

**Example:**
```python
# Source: tests/integration/test_case_terminal.py
@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_duplicate_terminal_prevention_regression(mocker, tmp_path):
    """Test duplicate prevention with REAL iTerm2 integration.

    NO MOCKING - uses real components:
    - Real Podman client and containers
    - Real Red Hat API calls
    - Real iTerm2 AppleScript execution
    - Real MacOSLauncher with find_window_by_title()

    Only mock TTY detection (pytest limitation).
    """
    # Real components
    podman_client = PodmanClient()
    api_client = RedHatAPIClient(access_token)
    launcher = get_launcher()  # Real MacOSLauncher

    # Only mock TTY check
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # First call creates window
    attach_terminal(case_number, config_manager, api_client, container_manager)

    # Second call should focus existing (not create duplicate)
    attach_terminal(case_number, config_manager, api_client, container_manager)

    # Assert: Window count didn't increase
    assert windows_after_second == windows_after_first
```

### Pattern 2: Test Isolation with Temporary Databases
**What:** Each test gets isolated registry/state database to prevent cross-test contamination
**When to use:** Testing WindowRegistry or StateDatabase operations

**Example:**
```python
# Source: tests/unit/test_window_registry.py
def test_register_and_lookup(tmp_path):
    """Test basic register and lookup operations."""
    # Use file-based database in tmp_path
    db = WindowRegistry(str(tmp_path / "test.db"))

    # Test operations
    success = db.register("12345678", "window-123", "iTerm2")
    assert success is True

    # Cleanup automatic via tmp_path fixture

def test_memory_database_isolation():
    """Test that :memory: databases are isolated per instance."""
    db1 = WindowRegistry(":memory:")
    db2 = WindowRegistry(":memory:")

    db1.register("12345678", "window-123", "iTerm2")

    # Should not exist in db2 (separate database)
    assert db2.lookup("12345678", lambda _: True) is None
```

### Pattern 3: Platform-Specific Test Skipping
**What:** Tests skip automatically on unsupported platforms using pytest.mark.skipif
**When to use:** Testing macOS-specific (AppleScript) or Linux-specific (wmctrl) features

**Example:**
```python
# Source: tests/integration/test_case_terminal.py
import platform
import pytest

@pytest.mark.integration
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Test requires macOS"
)
def test_duplicate_terminal_prevention_regression(mocker, tmp_path):
    """macOS-only test for iTerm2 duplicate prevention."""
    # iTerm2-specific testing
    pass

# Alternative: Custom markers in conftest.py
# conftest.py
import sys
import pytest

ALL = set("darwin linux win32".split())

def pytest_runtest_setup(item):
    supported_platforms = ALL.intersection(mark.name for mark in item.iter_markers())
    plat = sys.platform
    if supported_platforms and plat not in supported_platforms:
        pytest.skip(f"cannot run on platform {plat}")

# test_*.py
@pytest.mark.darwin
def test_macos_feature():
    pass

@pytest.mark.linux
def test_linux_feature():
    pass
```

### Pattern 4: Robust Cleanup with Finalizers
**What:** Ensure cleanup always runs even if test fails, using yield fixtures or request.addfinalizer
**When to use:** Tests creating real resources (containers, windows, registry entries)

**Example:**
```python
# Source: tests/integration/test_case_terminal.py (adapted)
@pytest.fixture
def container_cleanup(podman_client):
    """Fixture that ensures container cleanup."""
    containers_to_cleanup = []

    def register_container(container_name):
        containers_to_cleanup.append(container_name)

    yield register_container

    # Cleanup runs even if test fails
    for container_name in containers_to_cleanup:
        try:
            container = podman_client.client.containers.get(container_name)
            container.stop(timeout=2)
            container.remove()
        except Exception:
            pass  # Already cleaned up

def test_with_container(container_cleanup):
    """Test that uses container cleanup fixture."""
    container_name = "mc-99999999"
    container_cleanup(container_name)  # Register for cleanup

    # Test code that creates container
    # Cleanup guaranteed to run
```

### Pattern 5: Capturing Debug Output on Failure
**What:** Capture detailed state (registry snapshot, AppleScript logs, window state) when test fails
**When to use:** Complex integration tests that interact with external systems

**Example:**
```python
# Source: From CONTEXT decisions
import json
import tempfile
from datetime import datetime

@pytest.fixture
def debug_capture(request, tmp_path):
    """Capture debug information on test failure."""
    debug_dir = None

    yield  # Test runs

    # Check if test failed
    if request.node.rep_call.failed:
        # Create debug directory
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        debug_dir = Path(f"/tmp/mc-test-debug-{timestamp}/")
        debug_dir.mkdir(parents=True, exist_ok=True)

        # Capture registry state
        registry = WindowRegistry()
        # (Snapshot registry contents)

        # Capture window state (via AppleScript)
        # (Query iTerm/Terminal windows, IDs, titles)

        # Write debug artifacts
        with open(debug_dir / "test_context.json", "w") as f:
            json.dump({
                "test_name": request.node.name,
                "failure_reason": str(request.node.rep_call.longrepr),
                # ... other context
            }, f, indent=2)

        print(f"\nDebug artifacts saved to: {debug_dir}")

# Enable with:
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test result available to fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
```

### Anti-Patterns to Avoid
- **Mocking critical integration points:** Don't mock Podman, terminal launchers, or AppleScript in integration tests - this hides real bugs (like iTerm2 AppleScript name property limitation)
- **Shared state between tests:** Don't use shared registry/database without cleanup - leads to flaky tests and false positives/negatives
- **Ignoring platform differences:** Don't assume all tests run everywhere - use skip markers for platform-specific functionality
- **Silent cleanup failures:** Don't ignore cleanup exceptions - at minimum log them for debugging
- **Overly broad try/except:** Don't catch all exceptions without re-raising - makes debugging harder

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Temporary directories | Manual tempfile.mkdtemp + cleanup | pytest tmp_path fixture | Automatic cleanup, unique per test, proper permissions |
| Test data isolation | Copying test DB files | WindowRegistry(":memory:") or tmp_path DB | Parallel test support, no cleanup needed |
| Platform detection | Manual sys.platform checks everywhere | pytest.mark.skipif decorators | Centralized, documented, integrates with pytest -m |
| Cleanup on failure | Manual try/finally blocks | Yield fixtures or request.addfinalizer | Guaranteed cleanup, cleaner code |
| Coverage measurement | Manual coverage.py commands | pytest-cov plugin with pyproject.toml config | Better pytest integration, HTML reports, branch coverage |
| Mocking in pytest | Direct unittest.mock usage | pytest-mock mocker fixture | Automatic cleanup, pytest-style fixtures |
| Container cleanup | Manual Docker/Podman stop/rm | Session-scoped fixture with yield | Runs once, cleanup guaranteed |
| AppleScript execution | Raw subprocess.run everywhere | Wrapper methods with error handling | Centralized error handling, testability |

**Key insight:** Pytest's fixture system and plugin ecosystem solve most testing infrastructure problems. Don't build custom solutions - use fixtures, markers, and plugins.

## Common Pitfalls

### Pitfall 1: Race Conditions in Window Creation Tests
**What goes wrong:** Tests that create windows and immediately search for them fail because window creation is asynchronous
**Why it happens:** AppleScript returns before window is fully initialized, or command execution starts before title can be searched
**How to avoid:**
- Add explicit sleeps after window creation (e.g., `time.sleep(2)`)
- Use retry logic with timeout for window searches
- Capture window ID immediately after creation if possible
**Warning signs:** Intermittent test failures, "window not found" errors that disappear on retry

**Example:**
```python
# Bad: Immediate search fails
launcher.launch(options)
assert launcher.find_window_by_title(title)  # Fails!

# Good: Wait for window creation
launcher.launch(options)
time.sleep(2)  # Give iTerm2 time to create window
assert launcher.find_window_by_title(title)  # Succeeds
```

### Pitfall 2: Shared Registry State Between Tests
**What goes wrong:** Tests interfere with each other when using shared WindowRegistry database
**Why it happens:** Default WindowRegistry uses persistent file, previous test registrations leak into next test
**How to avoid:**
- Use WindowRegistry(":memory:") for unit tests (isolated per instance)
- Use WindowRegistry(str(tmp_path / "test.db")) for integration tests (isolated per test)
- Clean up test case registrations in teardown
**Warning signs:** Test passes in isolation but fails when run with full suite, non-deterministic failures

**Example:**
```python
# Bad: Shared state
def test_a():
    registry = WindowRegistry()  # Uses default file
    registry.register("12345678", "window-1", "iTerm2")

def test_b():
    registry = WindowRegistry()  # Same file!
    # Case 12345678 still registered from test_a
    assert registry.lookup("12345678", lambda _: True) is None  # Fails!

# Good: Isolated state
def test_a():
    registry = WindowRegistry(":memory:")  # Separate instance
    registry.register("12345678", "window-1", "iTerm2")

def test_b():
    registry = WindowRegistry(":memory:")  # Different instance
    assert registry.lookup("12345678", lambda _: True) is None  # Passes
```

### Pitfall 3: Container Cleanup Failures Cascade
**What goes wrong:** Test creates container but doesn't clean up, subsequent tests fail with "container already exists"
**Why it happens:** Exceptions during test prevent cleanup code from running, Podman containers persist
**How to avoid:**
- Use yield fixtures for cleanup (guaranteed to run)
- Use try/finally blocks with cleanup in finally
- Pre-cleanup: remove existing test containers before creating new ones
**Warning signs:** "container already exists" errors, accumulating containers in `podman ps -a`

**Example:**
```python
# Bad: Cleanup doesn't run on failure
def test_container():
    container = create_container("mc-99999999")
    assert something  # Fails, cleanup skipped
    cleanup_container(container)  # Never runs!

# Good: Cleanup guaranteed
@pytest.fixture
def test_container():
    container = create_container("mc-99999999")
    yield container
    cleanup_container(container)  # Always runs

# Better: Pre-cleanup
def test_container():
    # Remove if already exists
    try:
        existing = podman.containers.get("mc-99999999")
        existing.stop(timeout=2)
        existing.remove()
    except:
        pass

    container = create_container("mc-99999999")
    # ... test code
```

### Pitfall 4: Platform-Specific Tests Running on Wrong Platform
**What goes wrong:** macOS-only test runs on Linux CI, fails with confusing error
**Why it happens:** Forgot to add `@pytest.mark.skipif` decorator, test tries to import macOS-only modules
**How to avoid:**
- Always decorate platform-specific tests with skipif
- Use platform detection at test level, not import level
- Document platform requirements in test docstring
**Warning signs:** CI failures on specific platforms, "module not found" errors for platform-specific modules

**Example:**
```python
# Bad: Fails on Linux
def test_iterm_feature():
    from mc.terminal.macos import MacOSLauncher  # ImportError on Linux!
    launcher = MacOSLauncher()

# Good: Skips on Linux
import platform
import pytest

@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Test requires macOS"
)
def test_iterm_feature():
    from mc.terminal.macos import MacOSLauncher
    launcher = MacOSLauncher()
```

### Pitfall 5: Over-Mocking Integration Tests
**What goes wrong:** Integration test mocks so many components it no longer tests real integration
**Why it happens:** Mocking is easier than setting up real components, but defeats purpose of integration test
**How to avoid:**
- Mock external services (APIs) but not core components (Podman, launchers)
- Use real components for critical paths (window tracking, duplicate prevention)
- Only mock when necessary (TTY detection, network calls)
- Consider if test should be unit test instead if heavily mocked
**Warning signs:** Test passes but bug still exists in production, "integration" test that doesn't test integration

**Example from INTEGRATION_TEST_FIX_REPORT.md:**
```python
# Bad: Mocked too much, hid real iTerm2 bug
def test_duplicate_prevention(mocker):
    mock_launcher = mocker.MagicMock()
    mock_launcher.find_window_by_title.return_value = True  # Always returns True!
    mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)
    # Test passes but real AppleScript bug exists

# Good: Real components, found real bug
def test_duplicate_prevention(mocker):
    # Real launcher (no mock)
    launcher = get_launcher()  # Real MacOSLauncher

    # Only mock TTY check (pytest limitation)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Uses real AppleScript, discovered name property gets overwritten
    # Test correctly failed, revealed architectural issue
```

## Code Examples

Verified patterns from official sources and existing codebase:

### WindowRegistry Unit Testing
```python
# Source: tests/unit/test_window_registry.py
def test_stale_entry_removal():
    """Test auto-cleanup when validator returns False."""
    db = WindowRegistry(":memory:")
    db.register("12345678", "window-123", "iTerm2")

    # Validator returns False (window closed)
    def always_invalid(window_id):
        return False

    # Lookup returns None and removes entry
    window_id = db.lookup("12345678", always_invalid)
    assert window_id is None

    # Verify entry was removed
    def always_valid(window_id):
        return True

    window_id = db.lookup("12345678", always_valid)
    assert window_id is None
```

### Integration Test with Real Components
```python
# Source: tests/integration/test_case_terminal.py
@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
@pytest.mark.skipif(not _redhat_api_configured(), reason="Red Hat API not configured")
def test_case_terminal_end_to_end(mocker):
    """End-to-end test: terminal attachment workflow.

    Tests the entire stack with real components.
    Only mocks terminal launcher to avoid launching actual windows.
    """
    # Real components
    config = ConfigManager()
    salesforce_client = SalesforceAPIClient(...)
    podman_client = PodmanClient()
    container_manager = ContainerManager(podman_client, state_db)

    # Mock terminal launcher to avoid GUI interaction
    mock_launcher = mocker.MagicMock()
    mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)

    # Execute real workflow
    attach_terminal(
        case_number=test_case_number,
        config_manager=config,
        salesforce_client=salesforce_client,
        container_manager=container_manager,
    )

    # Verify launcher was called
    mock_launcher.launch.assert_called_once()

    # Cleanup real container
    container.stop(timeout=2)
    container.remove()
```

### Platform-Specific Skip Markers
```python
# Source: pytest official docs + existing tests
import platform
import sys
import pytest

# Method 1: Direct skipif
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Test requires macOS"
)
def test_macos_only():
    pass

@pytest.mark.skipif(
    sys.platform.startswith("linux"),
    reason="Test requires Linux"
)
def test_linux_only():
    pass

# Method 2: Custom markers in conftest.py
# conftest.py
ALL = set("darwin linux win32".split())

def pytest_runtest_setup(item):
    supported_platforms = ALL.intersection(mark.name for mark in item.iter_markers())
    plat = sys.platform
    if supported_platforms and plat not in supported_platforms:
        pytest.skip(f"cannot run on platform {plat}")

# test_*.py
@pytest.mark.darwin
def test_if_apple_feature():
    pass
```

### Cleanup Fixtures with Finalizers
```python
# Source: pytest documentation + pytest-docker pattern
@pytest.fixture(scope="session")
def podman_service():
    """Session-scoped fixture for Podman service.

    Ensures Podman is running for entire test session.
    """
    # Check if Podman is available
    client = PodmanClient()
    if not client.ping():
        pytest.skip("Podman not available")

    yield client

    # Session cleanup (if needed)
    # Note: Don't stop Podman service, just cleanup test containers

@pytest.fixture
def isolated_container(podman_service, request):
    """Function-scoped fixture for test container.

    Creates container, ensures cleanup even on failure.
    """
    container_name = f"mc-test-{request.node.name}"
    container = None

    try:
        container = podman_service.containers.create(...)
        yield container
    finally:
        # Cleanup guaranteed to run
        if container:
            try:
                container.stop(timeout=2)
                container.remove()
            except Exception as e:
                print(f"Cleanup warning: {e}")
```

### Parametrized Tests for Edge Cases
```python
# Source: pytest documentation
import pytest

@pytest.mark.parametrize("case_number,window_id,terminal_type", [
    # Normal cases
    ("12345678", "window-123", "iTerm2"),
    ("87654321", "window-456", "Terminal.app"),
    # Edge cases: special characters in window ID
    pytest.param("11111111", "0x1a2b3c4d", "xterm", id="hex-window-id"),
    # Edge cases: empty/None handling would be tested separately
])
def test_register_lookup_various_inputs(case_number, window_id, terminal_type):
    """Test registry with various input combinations."""
    db = WindowRegistry(":memory:")

    assert db.register(case_number, window_id, terminal_type) is True

    def always_valid(wid):
        return True

    assert db.lookup(case_number, always_valid) == window_id
```

### Debug Artifact Capture on Failure
```python
# Source: pytest documentation + CONTEXT decisions
import json
from pathlib import Path
from datetime import datetime

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test result available to fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

@pytest.fixture
def capture_on_failure(request, tmp_path):
    """Capture debug artifacts when test fails."""
    yield  # Test runs

    if hasattr(request.node, 'rep_call') and request.node.rep_call.failed:
        # Create debug directory
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        debug_dir = Path(f"/tmp/mc-test-debug-{timestamp}/")
        debug_dir.mkdir(parents=True, exist_ok=True)

        # Capture registry state
        try:
            from mc.terminal.registry import WindowRegistry
            registry = WindowRegistry()
            # Query all entries (would need to add _get_all_entries method)
            # Write to debug_dir / "registry_state.json"
        except Exception as e:
            print(f"Failed to capture registry state: {e}")

        # Capture test context
        with open(debug_dir / "test_context.json", "w") as f:
            json.dump({
                "test_name": request.node.name,
                "test_file": str(request.node.fspath),
                "failure_reason": str(request.node.rep_call.longrepr),
            }, f, indent=2)

        print(f"\n*** Debug artifacts saved to: {debug_dir} ***")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest framework | pytest framework | ~2018-2020 | Simpler syntax, better fixtures, extensive plugin ecosystem |
| coverage.py directly | pytest-cov plugin | ~2019 | Better pytest integration, automatic coverage in test runs |
| Manual test discovery | pytest auto-discovery | Always (pytest default) | Less boilerplate, conventions over configuration |
| Try/finally cleanup | Yield fixtures | ~2016 (pytest 3.0) | Cleaner code, guaranteed cleanup, better composability |
| unittest.mock | pytest-mock mocker fixture | ~2017 | Automatic cleanup, pytest-style fixtures |
| Blocking test execution | pytest-xdist parallel execution | ~2015+ | Faster test suites (careful with shared resources) |
| Manual skip logic | @pytest.mark.skipif decorators | Always (pytest core) | Declarative, documented, integrates with -m flag |

**Deprecated/outdated:**
- `pytest.config` (removed in pytest 5.0): Use `request.config` or `pytestconfig` fixture instead
- `pytest.mark.parametrize(scope='module')`: Scope parameter removed, use fixture scope instead
- `.pth file support in pytest-cov 7+`: Use coverage.py patch options for subprocess measurements
- `--strict` flag: Replaced by `--strict-markers` and `--strict-config` in pytest 6.0+

## Open Questions

Things that couldn't be fully resolved:

1. **Question: How to handle AppleScript test execution in CI/CD?**
   - What we know: CI/CD environments (GitHub Actions, etc.) don't have GUI/AppleScript access
   - What's unclear: Best way to handle platform-specific integration tests in CI
   - Recommendation: Use `@pytest.mark.skipif` for CI environments, run full suite locally + on macOS CI runners

2. **Question: Optimal balance between test speed and real component usage**
   - What we know: Real components (Podman, terminals) are slower but catch more bugs
   - What's unclear: Where to draw the line between unit tests (fast, mocked) and integration tests (slow, real)
   - Recommendation: Follow existing pattern - unit tests for logic, integration tests for critical paths (duplicate prevention, window tracking)

3. **Question: How to test WindowRegistry cleanup_stale_entries() without waiting for time-based staleness**
   - What we know: Method uses last_validated timestamp to determine staleness
   - What's unclear: How to test time-based logic without actual time delays or mocking time
   - Recommendation: Test the validation logic separately, mock time.time() for timestamp-based tests

4. **Question: Should pre-commit hooks run integration tests or only unit tests?**
   - What we know: CONTEXT says pre-commit hooks run tests automatically, but integration tests are slow
   - What's unclear: Which subset of tests should run in pre-commit vs. only in CI
   - Recommendation: Pre-commit runs fast tests only (unit + quick integration), full suite in CI

## Sources

### Primary (HIGH confidence)
- [pytest 9.0+ official documentation](https://docs.pytest.org/en/stable/) - Core framework features, fixtures, markers
- [pytest-cov official documentation](https://pytest-cov.readthedocs.io/) - Coverage configuration and best practices
- [pytest.mark.skipif documentation](https://docs.pytest.org/en/stable/how-to/skipping.html) - Platform-specific test skipping
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Fixture patterns and cleanup strategies
- Existing codebase:
  - `tests/unit/test_window_registry.py` - WindowRegistry unit test patterns
  - `tests/integration/test_case_terminal.py` - Integration test patterns with real components
  - `pyproject.toml` - pytest configuration, markers, coverage settings

### Secondary (MEDIUM confidence)
- [Integration Testing with pytest: Testing Real-World Scenarios](https://medium.com/@ujwalabothe/integration-testing-with-pytest-testing-real-world-scenarios-c506f4bf1bff) - Real components vs mocking guidance
- [How to Use pytest Parametrize](https://oneuptime.com/blog/post/2026-02-02-pytest-parametrize-guide/view) - Edge case organization (2026-02-02)
- [What is Setup and Teardown in Pytest?](https://pytest-with-eric.com/pytest-best-practices/pytest-setup-teardown/) - Cleanup strategies and finalizers
- [How to Use pytest Fixtures](https://oneuptime.com/blog/post/2026-02-02-pytest-fixtures/view) - Session-scoped fixtures for containers (2026-02-02)
- [End-to-End Python Integration Testing: A Complete Guide](https://www.testmu.ai/learning-hub/python-integration-testing/) - Integration testing best practices
- `.planning/INTEGRATION_TEST_FIX_REPORT.md` - Real-world lessons from fixing test_duplicate_terminal_prevention_regression

### Tertiary (LOW confidence)
- [Best Python Testing Tools 2026](https://medium.com/@inprogrammer/best-python-testing-tools-2026-updated-884dcb78b115) - Ecosystem overview
- [Pytest pre-commit hook](https://medium.com/@fistralpro/pytest-pre-commit-hook-b492edd0560e) - Pre-commit integration patterns
- [pre-commit vs. CI](https://switowski.com/blog/pre-commit-vs-ci/) - Trade-offs for test execution location

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest 9.0+ is industry standard, well-documented, stable
- Architecture: HIGH - Patterns verified in existing codebase and official docs
- Pitfalls: HIGH - Documented from real bugs (INTEGRATION_TEST_FIX_REPORT.md) and pytest docs
- Platform-specific testing: HIGH - Official pytest documentation and existing test examples
- Cleanup strategies: HIGH - pytest core feature, well-documented patterns

**Research date:** 2026-02-08
**Valid until:** 60 days (testing best practices stable, pytest ecosystem mature)

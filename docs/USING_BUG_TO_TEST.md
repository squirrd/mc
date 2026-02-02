# Using /bug-to-test in MC Project

**Purpose:** Convert UAT failures and production bugs into automated regression tests

**Project-Specific Guidance:** Based on UAT 1.1 experience (2026-02-02)

---

## Quick Start

```bash
# When you encounter a bug during UAT or production
/bug-to-test <error message or bug description>
```

**Example from UAT 1.1:**
```bash
/bug-to-test I get this failure running manual UAT test 1.1. This is the error:
```
➜  ~ mc case 04347611
Error: Failed to create container for case 04347611. Podman error: 'base_directory'
```
```

---

## Critical: Use REAL Components

**⚠️ IMPORTANT:** When `/bug-to-test` asks about test implementation, ALWAYS request:

> "Use real components - no mocks except TTY check"

### Why This Matters

From UAT 1.1 experience:
- **With mocks:** Would miss the actual `KeyError` in config access
- **With real components:** Caught exact bug users experience

### What to Tell the Agent

When `/bug-to-test` is creating your test, specify:

```
Create integration test with:
- ✅ Real Red Hat API client (actual HTTP calls)
- ✅ Real Podman client (actual container operations)
- ✅ Real ConfigManager (actual file I/O)
- ✅ Real StateDatabase (actual SQLite)
- ✅ Real filesystem (use tmp_path for isolation)
- ⚠️ Mock only TTY check (pytest limitation)

Do NOT mock API clients, Podman, database, or file operations.
```

---

## Project-Specific Test Patterns

### Pattern 1: Fresh Install Scenario

**Use Case:** Testing behavior with minimal/missing config

```python
@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman required")
@pytest.mark.skipif(not _redhat_api_configured(), reason="API credentials required")
def test_<feature>_fresh_install_regression(mocker, tmp_path):
    """Regression test for <UAT X.Y> - Fresh install scenario."""

    # Create minimal config (only API token, like after wizard)
    minimal_config = {
        "api": {
            "rh_api_offline_token": real_cfg["api"]["rh_api_offline_token"]
        }
        # Intentionally missing other keys to test defaults
    }

    # Real components with isolated paths
    config_manager = ConfigManager()
    config_manager._config_path = tmp_path / "config" / "config.toml"

    # Real API client
    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # Real Podman
    podman_client = PodmanClient()
    state_db = StateDatabase(str(tmp_path / "state" / "containers.db"))
    container_manager = ContainerManager(podman_client, state_db)

    # Only mock TTY
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Test real workflow...
```

### Pattern 2: API Integration Scenario

**Use Case:** Testing Red Hat API integration

```python
@pytest.mark.integration
@pytest.mark.skipif(not _redhat_api_configured(), reason="API credentials required")
def test_<feature>_api_integration_regression(tmp_path):
    """Regression test for <Bug #XYZ> - API integration."""

    # Real API client, real HTTP calls
    config = ConfigManager().load()
    access_token = get_access_token(config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # Real API call
    case_details = api_client.get_case("04347611")

    # Verify real response
    assert "summary" in case_details
    assert "account" in case_details
```

### Pattern 3: Container Lifecycle Scenario

**Use Case:** Testing Podman container operations

```python
@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman required")
def test_<feature>_container_lifecycle_regression(tmp_path):
    """Regression test for <UAT X.Y> - Container lifecycle."""

    # Real Podman client
    podman_client = PodmanClient()
    state_db = StateDatabase(str(tmp_path / "state" / "containers.db"))
    container_manager = ContainerManager(podman_client, state_db)

    container = None
    try:
        # Real container creation
        container_manager.create(
            case_number="99999999",
            workspace_path=str(tmp_path / "workspace"),
            customer_name="Test Customer"
        )

        # Verify real container exists
        container = podman_client.client.containers.get("mc-99999999")
        assert container.status in ("running", "configured")

    finally:
        # Real cleanup
        if container:
            container.stop(timeout=2)
            container.remove()
```

---

## Checklist for /bug-to-test

When creating a regression test with `/bug-to-test`:

### Phase 1: Bug Analysis
- [ ] Provide exact error message
- [ ] Specify UAT test number (if applicable)
- [ ] Indicate platform (macOS/Linux/Both)
- [ ] Describe severity (Critical/Major/Minor)

### Phase 2: Test Requirements
- [ ] Request "real components, minimal mocking"
- [ ] Specify which API/service to use (Red Hat API, Podman, etc.)
- [ ] Indicate if test should launch real terminal
- [ ] Provide test case number to use (e.g., "04347611")

### Phase 3: Documentation
- [ ] Ensure test has comprehensive docstring with:
  - [ ] Bug discovery date
  - [ ] Platform
  - [ ] Severity
  - [ ] Problem description
  - [ ] Root cause
  - [ ] Steps to reproduce
  - [ ] Expected vs actual behavior
  - [ ] UAT test reference (if applicable)
- [ ] UAT document updated with test reference
- [ ] REGRESSION_TESTS.md updated

### Phase 4: Verification
- [ ] Test runs without syntax errors
- [ ] Test reproduces the bug (should fail before fix)
- [ ] Test uses real components (no unnecessary mocks)
- [ ] Test has proper cleanup (containers, files)
- [ ] Test has skip conditions for CI

---

## Common UAT Scenarios

### UAT 1.x: Fresh Install Tests
```python
# Minimal config, test defaults and lazy initialization
minimal_config = {"api": {"rh_api_offline_token": token}}
```

### UAT 2.x: Workspace Path Tests
```python
# Real Podman, verify mount paths and file sync
container = podman_client.client.containers.get(container_name)
```

### UAT 3.x: Container Image Tests
```python
# Real image pull, verify error messages
podman_client.pull_image("quay.io/...")
```

### UAT 4.x: Quay.io Auto-Pull Tests
```python
# Real image operations, measure pull time
start = time.time()
result = container_manager.create(...)
duration = time.time() - start
```

### UAT 5.x: Terminal Tests
```python
# Can mock launcher OR let it launch real terminal
# Decision: For terminal integration bugs → real terminal
#           For other features → can mock
```

---

## Skip Conditions

Tests created by `/bug-to-test` should use appropriate skip conditions:

```python
def _podman_available() -> bool:
    """Check if Podman is available."""
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False

def _redhat_api_configured() -> bool:
    """Check if Red Hat API credentials configured."""
    try:
        config = ConfigManager()
        if not config.exists():
            return False
        cfg = config.load()
        return bool(cfg.get("api", {}).get("rh_api_offline_token"))
    except Exception:
        return False

@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
@pytest.mark.skipif(not _redhat_api_configured(), reason="API credentials not configured")
def test_regression(...):
    ...
```

---

## File Organization

```
tests/integration/
├── test_case_terminal.py          # Terminal attachment tests
├── test_container_create_integration.py  # Container creation tests
├── test_config_migration.py       # Config migration tests
├── test_container_image.py        # Image pull tests
└── REGRESSION_TESTS.md           # Index of all regression tests

.planning/
└── UAT-TESTS-BATCH-ABCE.md       # Manual UAT tests with automation links
```

---

## Example: Full /bug-to-test Session

```
User: /bug-to-test I get this failure running manual UAT test 1.1:
      Error: Failed to create container. Podman error: 'base_directory'

Agent: [Asks questions about platform, severity, environment]

User: macOS, Critical, followed exact UAT 1.1 steps (fresh install)

Agent: [Analyzes UAT 1.1, identifies root cause]
       Found issue in src/mc/terminal/attach.py:165
       Uses config_manager.load()["base_directory"] without default

Agent: [Asks about test approach]

User: Use real components - Red Hat API, Podman, Config, Database
      Only mock TTY check
      Launch real terminal window

Agent: [Creates test with real components]
       - Real API client
       - Real Podman client
       - Real config file (tmp_path)
       - Real database (tmp_path)
       - Proper cleanup

Agent: [Runs test]
       ✗ Test FAILS - successfully reproduces bug!
       Error: KeyError: 'base_directory'

Agent: [Updates documentation]
       - UAT doc updated
       - REGRESSION_TESTS.md created
       - Commits with detailed context

Agent: Test created! Will pass once you fix lines 165 & 200 in attach.py
       Use: config_manager.get("base_directory", os.path.expanduser("~/mc"))
```

---

## Next Steps After /bug-to-test

1. **Test created and failing** (reproduces bug)
   ```bash
   uv run pytest tests/integration/test_X.py::test_Y -v
   # Should FAIL with exact bug error
   ```

2. **Fix the bug** in source code
   ```bash
   # Edit source files based on test's root cause analysis
   ```

3. **Verify fix**
   ```bash
   uv run pytest tests/integration/test_X.py::test_Y -v
   # Should PASS now
   ```

4. **Run related tests**
   ```bash
   uv run pytest tests/integration/test_X.py -v
   # Ensure no regressions
   ```

5. **Update documentation**
   ```markdown
   # In REGRESSION_TESTS.md
   - Status: Failing → Passing
   - Fixed in: v2.0.2
   ```

6. **Commit the fix**
   ```bash
   git commit -m "fix: <description>

   Fixes integration test: test_Y
   Root cause: <explanation>
   ```

---

## See Also

- `docs/INTEGRATION_TEST_BEST_PRACTICES.md` - Detailed best practices
- `tests/integration/REGRESSION_TESTS.md` - All regression tests
- `.planning/UAT-TESTS-BATCH-ABCE.md` - Manual UAT tests

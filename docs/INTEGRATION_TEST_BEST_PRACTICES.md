# Integration Test Best Practices

**Last Updated:** 2026-02-02
**Based on:** Real experience with UAT 1.1 regression test creation

---

## Core Principle: Real Components, Not Mocks

**❌ AVOID:** Over-mocking in integration tests
**✅ PREFER:** Using real components whenever possible

### Why Real Components Matter

Integration tests should test how components work **together**, not in isolation. The goal is to catch real bugs that happen when systems integrate.

**Example from UAT 1.1:**

```python
# ❌ BAD: Over-mocked integration test
def test_fresh_install_with_mocks(mocker):
    mock_api = mocker.MagicMock()  # Not hitting real API
    mock_config = mocker.MagicMock()  # Not loading real config
    mock_podman = mocker.MagicMock()  # Not talking to Podman
    # This tests mocks interacting with mocks, not real integration!

# ✅ GOOD: Real integration test
def test_fresh_install_real_components(tmp_path):
    # Real config file (in temp location)
    config_manager = ConfigManager()
    config_manager._config_path = tmp_path / "config.toml"

    # Real API client (makes actual HTTP calls)
    api_client = RedHatAPIClient(access_token)

    # Real Podman client (talks to actual Podman daemon)
    podman_client = PodmanClient()

    # Real container manager
    container_manager = ContainerManager(podman_client, state_db)

    # This tests real integration!
```

---

## What To Mock vs What To Keep Real

### ✅ Keep Real (Integration Tests)

1. **API Clients**
   - Red Hat API client
   - Salesforce API client
   - Make real HTTP calls (use test accounts if needed)
   - **Benefit:** Catches API contract changes, authentication issues

2. **Database Connections**
   - SQLite databases
   - State databases
   - Use `tmp_path` for isolation, but real DB engine
   - **Benefit:** Catches SQL syntax errors, schema issues

3. **File System Operations**
   - Config file loading/saving
   - Workspace directory creation
   - Use `tmp_path` for isolation, but real filesystem
   - **Benefit:** Catches permission issues, path problems

4. **Container Operations**
   - Podman client
   - Container creation/management
   - Real containers (clean up in `finally` block)
   - **Benefit:** Catches container runtime issues, mount problems

5. **Shell Commands**
   - Bash execution
   - Git commands
   - Terminal operations
   - **Benefit:** Catches command syntax, environment issues

### ⚠️ Mock Only When Necessary

1. **TTY Detection**
   ```python
   # pytest doesn't run in a TTY, so must mock this
   mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)
   ```

2. **Terminal Launching** (Optional)
   ```python
   # Can mock to avoid windows popping up, OR
   # Let it launch real terminal for full integration test
   # Decision: If testing terminal integration → keep real
   #           If testing other features → can mock
   ```

3. **External Services You Don't Control**
   - Third-party APIs without test environments
   - Payment processors
   - Only when absolutely necessary

4. **Time-Based Operations**
   ```python
   # For testing cache expiry, uptime calculations
   mocker.patch("time.time", return_value=fixed_timestamp)
   ```

---

## Integration Test Checklist

When creating an integration test (like with `/bug-to-test`), ask:

- [ ] Am I testing how real components work together?
- [ ] Can I use real API clients? (Yes → do it)
- [ ] Can I use real database? (Yes → use tmp_path)
- [ ] Can I use real Podman? (Yes → do it, cleanup in finally)
- [ ] Can I use real file system? (Yes → use tmp_path)
- [ ] What do I **need** to mock? (As little as possible)
- [ ] Does this test catch real integration bugs?
- [ ] Can this run in CI? (Skip with pytest.mark.skipif if needs credentials)

---

## Pattern: Real Components with Isolated State

**Goal:** Use real components but isolate test state

```python
@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman required")
@pytest.mark.skipif(not _redhat_api_configured(), reason="API credentials required")
def test_real_integration(tmp_path):
    """Full integration test with real components, isolated state."""

    # Setup: Isolated directories
    test_config_dir = tmp_path / "config"
    test_state_dir = tmp_path / "state"
    test_config_dir.mkdir()
    test_state_dir.mkdir()

    # Real config manager, isolated path
    config_manager = ConfigManager()
    config_manager._config_path = test_config_dir / "config.toml"

    # Write minimal real config
    with open(config_manager._config_path, "wb") as f:
        tomli_w.dump(minimal_config, f)

    # Real API client with real credentials
    real_config = ConfigManager().load()
    access_token = get_access_token(real_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # Real Podman client
    podman_client = PodmanClient()

    # Real state database (isolated path)
    state_db = StateDatabase(str(test_state_dir / "containers.db"))

    # Real container manager
    container_manager = ContainerManager(podman_client, state_db)

    # Mock only TTY (pytest limitation)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    container = None
    try:
        # Execute real workflow
        attach_terminal(
            case_number="04347611",
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        # Verify with real components
        container = podman_client.client.containers.get(f"mc-04347611")
        assert container.status in ("running", "configured")

        metadata = state_db.get_container("04347611")
        assert metadata is not None

    finally:
        # Cleanup real resources
        if container:
            container.stop(timeout=2)
            container.remove()
```

**Key Points:**
- ✅ Real API calls
- ✅ Real Podman operations
- ✅ Real database
- ✅ Real config files
- ✅ Isolated state (tmp_path)
- ✅ Proper cleanup
- ⚠️ Only mocks TTY check

---

## Skip Conditions for CI

Integration tests with real components may need credentials or services:

```python
@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available - install and start Podman"
)
@pytest.mark.skipif(
    not _redhat_api_configured(),
    reason="Red Hat API credentials not configured - run: mc config wizard"
)
def test_with_real_components(tmp_path):
    # Test requires Podman running AND API credentials
    ...
```

**CI Environment Variables:**
```bash
# In CI, set these to run integration tests
export MC_TEST_INTEGRATION=1
export RH_API_OFFLINE_TOKEN=<token>

# Tests will skip if not set
```

---

## Test Naming Convention

```python
def test_<feature>_<scenario>_regression(tmp_path):
    """Regression test for <UAT X.Y / Bug #123> - <description>

    Bug discovered: YYYY-MM-DD
    Platform: macOS / Linux / Both
    Severity: Critical / Major / Minor

    Problem:
    <What went wrong>

    Root cause:
    <Why it happened>

    Test approach:
    - Uses real API client for case metadata
    - Uses real Podman client for containers
    - Uses real database (isolated via tmp_path)
    - Only mocks TTY check (pytest limitation)

    This test will fail until bug is fixed, then pass automatically.
    """
```

---

## Benefits of Real Components

From UAT 1.1 experience:

**We discovered:**
```
Error: Failed to create container for case 04347611. Podman error: 'base_directory'
```

**With mocks, we might have missed:**
- ❌ Wouldn't catch `KeyError` in config access
- ❌ Wouldn't catch Podman connection issues
- ❌ Wouldn't catch API authentication problems
- ❌ Wouldn't catch workspace path creation issues
- ❌ Wouldn't catch real terminal launching issues

**With real components, we caught:**
- ✅ Config file missing key (KeyError)
- ✅ Exact error message users see
- ✅ Full integration flow from API → Container → Terminal
- ✅ Real Podman behavior
- ✅ Real filesystem operations

---

## When To Use Unit Tests vs Integration Tests

**Unit Tests** (src/mc/):
- Single function/class behavior
- Mock external dependencies
- Fast (<1ms per test)
- Test edge cases, error paths
- **Goal:** Verify logic in isolation

**Integration Tests** (tests/integration/):
- Multiple components working together
- Real external dependencies (when possible)
- Slower (100ms-5s per test)
- Test real workflows
- **Goal:** Verify system works end-to-end

**Regression Tests** (subset of integration):
- Created from real bugs
- Reproduce exact failure scenario
- Real components
- Comprehensive docstring with bug history
- **Goal:** Prevent bug from returning

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Mocking Everything

```python
# This is NOT an integration test, it's a unit test with mocks
def test_container_create(mocker):
    mock_podman = mocker.MagicMock()
    mock_config = mocker.MagicMock()
    mock_api = mocker.MagicMock()
    # Testing mocks, not integration!
```

### ❌ Mistake 2: No Cleanup

```python
def test_container_create():
    container = create_container("12345678")
    # Missing cleanup! Container left running
```

### ❌ Mistake 3: Hardcoded Paths

```python
def test_config_load():
    config = ConfigManager()
    config._config_path = "/tmp/test.toml"  # ❌ Not isolated, race conditions
```

### ✅ Solution: Use pytest fixtures

```python
def test_container_create(tmp_path):
    container = None
    try:
        container = create_container("12345678")
        assert container.status == "running"
    finally:
        if container:
            container.stop()
            container.remove()

def test_config_load(tmp_path):
    config_path = tmp_path / "config.toml"  # ✅ Isolated per test
```

---

## Summary

**Golden Rule:** If it can be real, make it real.

**Mantra:** Integration tests test integration. Mock as little as possible.

**When in doubt:** Ask "Does this mock hide a real bug?" If yes, don't mock it.

---

## See Also

- `tests/integration/test_case_terminal.py::test_fresh_install_missing_config_base_directory_regression` - Example of real integration test
- `tests/integration/REGRESSION_TESTS.md` - Regression test index
- `.planning/UAT-TESTS-BATCH-ABCE.md` - UAT tests that drive regression tests

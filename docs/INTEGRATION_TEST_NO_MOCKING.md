# Integration Tests: The No-Mocking Rule

## Core Principle

**Integration tests must use REAL components. Do not mock.**

This is not a suggestion. This is a hard requirement.

## Why This Matters

### The Problem with Mocking

When you mock components in an integration test, you're testing **what you think should happen**, not **what actually happens**.

**Example - UAT 5.2 Duplicate Terminal Prevention:**

**With Mocking (Wrong):**
```python
# Mock the launcher
mock_launcher = mocker.MagicMock()
mock_launcher.find_window_by_title.return_value = True  # Simulate finding window
mock_launcher.launch.side_effect = lambda x: created_windows.append(x.title)

# Test passes! ✓
# But real bug still exists in production ✗
```

Result: Test **passes** but bug **exists**. The mock simulates correct behavior while the real iTerm2 AppleScript is broken.

**Without Mocking (Correct):**
```python
# Use REAL launcher with REAL iTerm2 AppleScript
from mc.terminal.launcher import get_launcher
launcher = get_launcher()  # Returns real MacOSLauncher

# First call: Creates real iTerm2 window
attach_terminal(...)

# Test if we can find it
found = launcher.find_window_by_title(title)  # REAL AppleScript execution

if not found:
    pytest.fail("BUG: Just created window but can't find it!")  # ✗ Test catches the bug!
```

Result: Test **fails** because real bug exists. The real AppleScript search doesn't find the window it just created.

### What We Learned

In UAT 5.2, we initially created a test with mocks. The test passed. We thought "logic is correct, integration must work."

**Wrong.**

The real bug was in the iTerm2 AppleScript layer. The mocked test couldn't catch it because:
1. Mock simulated "perfect" window finding
2. Mock returned True when it should return False
3. Test validated Python logic only, not the actual integration

When we removed the mocks and used real iTerm2:
- Test immediately failed
- Bug location became obvious
- Root cause identified in minutes

## The Rules

### ✅ ALWAYS Keep Real

Use real components for:

1. **External Services:**
   - Red Hat API client (real HTTP calls)
   - Salesforce API (real authentication)
   - Any third-party API

2. **System Integration:**
   - Podman client (real container operations)
   - Terminal launcher (real AppleScript execution)
   - File system operations (use tmp_path for isolation)

3. **Internal Components:**
   - Config manager (real file I/O)
   - State database (real SQLite)
   - Container manager (real lifecycle operations)

4. **Platform Integration:**
   - macOS AppleScript (real osascript execution)
   - Terminal emulators (real iTerm2/Terminal.app)
   - Shell operations (real bash execution)

### ⚠️ ONLY Mock When Absolutely Necessary

You may ONLY mock:

1. **TTY Detection:**
   ```python
   # pytest doesn't run in TTY - this is a limitation of the test environment
   mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)
   ```

2. **Time-based Operations (for determinism):**
   ```python
   # Make tests deterministic
   mocker.patch("time.time", return_value=1234567890.0)
   ```

3. **External Services You Don't Control:**
   - Payment processors
   - Third-party webhooks you can't trigger
   - Services that require specific test accounts

4. **Dangerous Operations:**
   - Production database writes
   - Permanent system modifications
   - Cloud resource creation (unless test environment)

### ❌ NEVER Mock

**DO NOT mock these under any circumstances:**

1. Your own code components
2. API clients you wrote
3. Database operations (use test databases instead)
4. File system operations (use tmp_path instead)
5. Container operations (use real containers, clean them up)
6. Terminal/shell integration (the whole point of integration tests!)

## How to Write Integration Tests Without Mocking

### Pattern 1: Use Temporary Resources

Instead of mocking file operations:

```python
# ❌ BAD - Mocking
mock_file = mocker.MagicMock()
mock_file.read.return_value = "test data"

# ✅ GOOD - Real files with isolation
def test_something(tmp_path):
    test_file = tmp_path / "config.toml"
    test_file.write_text("test data")

    # Use REAL config manager with REAL file
    config = ConfigManager()
    config._config_path = test_file
    result = config.load()  # Real file I/O
```

### Pattern 2: Use Test Credentials

Instead of mocking API clients:

```python
# ❌ BAD - Mocking
mock_api = mocker.MagicMock()
mock_api.get_case.return_value = {"summary": "test"}

# ✅ GOOD - Real API with test account
def test_something():
    # Load REAL credentials from environment or config
    config = ConfigManager()
    token = config.get("api", {}).get("rh_api_offline_token")

    # Make REAL API call
    api_client = RedHatAPIClient(token)
    case = api_client.get_case("04347611")  # Real HTTP request
```

### Pattern 3: Clean Up Real Resources

Instead of mocking resource creation:

```python
# ❌ BAD - Mocking
mock_container = mocker.MagicMock()
mock_podman.create_container.return_value = mock_container

# ✅ GOOD - Real containers with cleanup
def test_something():
    podman = PodmanClient()

    try:
        # Create REAL container
        container = podman.create_container(...)

        # Test real container operations
        result = container.exec_run("ls /case")

    finally:
        # Always clean up
        container.stop()
        container.remove()
```

### Pattern 4: Accept Side Effects

Integration tests have side effects. That's the point.

```python
# ✅ GOOD - Accept that iTerm2 windows will open
def test_duplicate_terminal_prevention():
    """
    WARNING: This test will launch REAL iTerm2 windows!
    Manual cleanup required after test.
    """

    # First call: Opens real iTerm2 window
    attach_terminal(case_number="04347611")

    # Second call: Should focus existing window (REAL AppleScript test)
    attach_terminal(case_number="04347611")

    # Verify with REAL window count
    window_count = count_iterm2_windows()

    print("⚠️  MANUAL CLEANUP REQUIRED:")
    print("Please close the iTerm2 test window")
```

## When Tests Are "Too Integrated"

**Question:** "This test is slow and has side effects. Should I mock to make it faster?"

**Answer:** No. You should:

1. **Use skip marks for expensive tests:**
   ```python
   @pytest.mark.integration
   @pytest.mark.skipif(not os.getenv("MC_TEST_INTEGRATION"), reason="Expensive test")
   ```

2. **Run fast unit tests by default, integration tests on demand:**
   ```bash
   # Fast: Run unit tests only
   pytest tests/unit/

   # Slow: Run integration tests
   MC_TEST_INTEGRATION=1 pytest tests/integration/
   ```

3. **Accept that integration tests are slow:**
   - Unit tests are fast (milliseconds)
   - Integration tests are slow (seconds to minutes)
   - That's expected and correct

## Exceptions That Prove the Rule

There are exactly **three** scenarios where mocking in integration tests is acceptable:

### 1. Environment Limitations (TTY)
```python
# pytest doesn't provide TTY - this is a test environment limitation
mocker.patch("sys.stdout.isatty", return_value=True)
```

### 2. Non-Determinism (Time, Random)
```python
# Make tests deterministic
mocker.patch("time.time", return_value=1234567890.0)
mocker.patch("random.randint", return_value=42)
```

### 3. External Dependencies You Can't Control
```python
# Third-party webhook that requires manual triggering
mocker.patch("stripe.Webhook.construct_event", return_value=test_event)
```

If your mock doesn't fit one of these three categories, **you're doing it wrong**.

## How to Know If You're Mocking Too Much

Ask yourself:

1. **"Am I mocking my own code?"**
   - If yes, stop. Use real components.

2. **"Could this mock hide a bug?"**
   - If yes, remove the mock and use real integration.

3. **"Does this mock make assumptions about behavior?"**
   - If yes, those assumptions might be wrong. Test the real behavior.

4. **"Am I testing what I think should happen, or what actually happens?"**
   - Mocks test expectations. Real components test reality.

## The Test Quality Hierarchy

From worst to best:

1. **❌ Over-mocked integration test:** Tests nothing, hides bugs, gives false confidence
2. **⚠️ Unit test:** Tests one component in isolation, useful but limited
3. **✅ True integration test:** Tests real components together, catches real bugs

Don't write #1 thinking it's #3.

## Examples from This Project

### Example 1: UAT 1.1 - Fresh Install (Correct)

```python
def test_fresh_install_no_old_directories_created_regression(mocker, tmp_path):
    # ✅ Real config file
    config_path = tmp_path / "config.toml"
    with open(config_path, "wb") as f:
        tomli_w.dump(minimal_config, f)

    # ✅ Real config manager
    config_manager = ConfigManager()
    config_manager._config_path = config_path

    # ✅ Real API client with real HTTP calls
    api_client = RedHatAPIClient(access_token)

    # ✅ Real Podman client
    podman_client = PodmanClient()

    # ✅ Real state database
    state_db = StateDatabase(str(db_path))

    # ⚠️ ONLY mock TTY (pytest limitation)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)
```

**Result:** Caught real bug where bashrc was created in wrong directory.

### Example 2: UAT 5.2 - Duplicate Prevention (Fixed)

**Before (Wrong):**
```python
# ❌ Mocked launcher - test passed, bug existed
mock_launcher = mocker.MagicMock()
mock_launcher.find_window_by_title.return_value = True
```

**After (Correct):**
```python
# ✅ Real launcher with real iTerm2
from mc.terminal.launcher import get_launcher
launcher = get_launcher()  # Real MacOSLauncher

# Real window creation
attach_terminal(...)

# Real window search - THIS IS WHERE THE BUG IS
found = launcher.find_window_by_title(title)  # Returns False when should return True

if not found:
    pytest.fail("BUG: Can't find window we just created!")  # Catches the actual bug!
```

**Result:** Test now catches the real iTerm2 AppleScript bug.

## Summary

**Integration tests test integration.**

If you're mocking the integration, you're not testing anything useful.

Use real components. Accept side effects. Clean up properly.

Your tests will be slower, but they'll catch real bugs that mocked tests miss.

**The goal is not fast tests. The goal is correct software.**

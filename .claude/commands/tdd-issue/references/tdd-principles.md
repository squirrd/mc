# TDD Principles Reference

Reference material for the tdd-issue skill. These principles govern all decisions
made during the Red-Green-Refactor cycle.

---

## Red-Green-Refactor

| Phase | What you do | Rule |
|---|---|---|
| **RED** | Write a failing test | Test must fail for the RIGHT reason |
| **GREEN** | Write minimum code to pass | Fake it till you make it — get green fast |
| **REFACTOR** | Clean up — no behaviour changes | Test must still pass after refactoring |

The cycle is short and tight. Each iteration adds exactly one behaviour.

**Red must be genuine:**
- If a new test passes immediately, it does not test the right thing
- Re-examine the assertion and the code path being exercised
- A passing test before the fix means either the bug is not reproduced or the test is wrong

**Green must be minimal:**
- The simplest code that makes the test pass is correct here
- Resist the urge to design — that belongs in Refactor
- Do NOT fix other bugs or add features while in Green phase

**Refactor is safe:**
- Because the test is green, you have a safety net
- Change structure, not behaviour
- Run tests after every refactor step (not just at the end)

---

## Testing Pyramid

```
         /\
        /E2E\          ← Slowest, fewest, most brittle — avoid adding here
       /------\
      /Integr. \       ← Tests real components working together
     /----------\
    /  Unit      \     ← Fastest, most numerous, most precise
   /--------------\
```

**Unit tests** (tests/unit/):
- One function or class in isolation
- External dependencies mocked
- Run in milliseconds
- Pinpoint the exact failure

**Integration tests** (tests/integration/):
- Multiple real components interacting
- No mocking of the system under test
- May be slower (file I/O, network, database)
- The acceptance criterion for a bug fix

**E2E tests:**
- Not currently used in this project
- Integration tests serve this role where needed

---

## Core Mindsets

### Tests as documentation
A well-written test tells the story of what the code should do.
The docstring is not optional — it captures:
- What the bug was
- When it was found
- What behaviour is now guaranteed

### Tests as a safety net
Every bug fixed with a test means that bug cannot silently return.
Coverage is not a metric to chase — it is a consequence of writing good tests.

### Fake it till you make it (Green phase)
Return a hardcoded value. Special-case the test input. That's fine.
Refactor immediately after to generalise.
This forces you to see that the test drives the design, not the other way around.

### Test one thing
Each test should have one logical assertion.
Multiple `assert` statements are fine if they all test the same behaviour.
If you need separate assertions for separate behaviours: write separate tests.

---

## Pytest Quick Reference

### Parametrize

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("case-1",  "result-1"),
    ("case-2",  "result-2"),
    ("edge",    "edge-result"),
])
def test_something(input, expected):
    assert my_function(input) == expected
```

### MagicMock

```python
from unittest.mock import MagicMock, patch

# Mock a return value
mock_client = MagicMock()
mock_client.get_case.return_value = {"id": "12345678", "subject": "Test"}

# Mock a method that raises
mock_client.connect.side_effect = ConnectionError("timeout")

# Patch at the point of use (not the point of definition)
with patch("mc.controller.workspace.SalesforceClient") as mock_sf:
    mock_sf.return_value = mock_client
    result = do_thing()

assert result == expected
```

### Project test markers

```python
@pytest.mark.integration          # Requires real Podman, file system, etc.
@pytest.mark.backwards_compatibility  # Tests a public API contract
```

### Fixtures (conftest.py)

```python
@pytest.fixture
def case_number():
    return "12345678"

@pytest.fixture
def mock_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\n')
    return config_file
```

### Useful pytest flags

```bash
uv run pytest tests/unit/test_foo.py::test_bar  -v -s --no-cov   # single test, verbose, no coverage
uv run pytest tests/unit/ -v --no-cov -q                          # all unit tests, quiet
uv run pytest -m "not integration"                                 # skip integration tests
uv run pytest --co -q                                              # collect only — list tests
```

# Stack Research: Python CLI Tool Hardening

**Domain:** Python CLI tool production hardening
**Researched:** 2026-01-20
**Confidence:** MEDIUM (based on training data from 2025, official Python docs verified for logging)

## Overview

This research focuses on the **hardening stack** for an existing Python 3.8+ CLI tool. The application stack (requests, argparse) already exists. This document covers testing, type checking, linting, logging, and performance tools needed to make the codebase production-ready.

**Existing foundation:**
- Python 3.8+ (configured for 3.8-3.11 in pyproject.toml)
- pytest 7.0+ (configured but unused)
- mypy 1.0+ (configured with minimal settings)
- black 23.0+ (configured)
- flake8 6.0+ (configured)

**Goal:** Upgrade this foundation to 2025 best practices with comprehensive testing, type safety, and observability.

---

## Recommended Stack

### Core Testing Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pytest** | 8.0+ | Test runner and framework | Industry standard, rich plugin ecosystem, excellent CLI output, built-in fixtures system. Already configured. |
| **pytest-cov** | 5.0+ | Coverage reporting | Integrates coverage.py with pytest, shows untested code, industry standard for coverage. Already configured. |
| **pytest-mock** | 3.14+ | Mocking utilities | Provides `mocker` fixture wrapping unittest.mock, cleaner syntax than raw mock, essential for testing external dependencies like `requests`. |
| **pytest-xdist** | 3.5+ | Parallel test execution | Runs tests across multiple CPUs, critical for fast CI/CD, 4-8x speedup on multi-core systems. |

**Confidence:** HIGH (pytest ecosystem is stable and well-documented)

### HTTP Mocking

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **responses** | 0.25+ | HTTP request mocking | Mock `requests` library calls, simpler than pytest-mock for HTTP, declarative API responses. **Primary choice for this project.** |
| **requests-mock** | 1.11+ | Alternative HTTP mocking | Alternative to responses, more fixture-based, better pytest integration via `requests_mock` fixture. |
| **vcrpy** | 6.0+ | Record/replay HTTP | Record real API responses once, replay in tests. Good for integration tests with real APIs. |

**Recommendation:** Use **responses** for unit tests (simple, clean), **vcrpy** for integration tests (real API interaction recording).

**Confidence:** HIGH (well-established libraries with stable APIs)

### Type Checking

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **mypy** | 1.10+ | Static type checker | Already configured. Need to enable stricter settings: `disallow_untyped_defs=true`, `strict_optional=true`, `warn_redundant_casts=true`. |
| **types-requests** | 2.31+ | Type stubs for requests | Provides complete type hints for requests library, eliminates mypy errors for HTTP code. |

**Current gap:** pyproject.toml has mypy with `disallow_untyped_defs = false`. Need to enable progressive typing.

**Confidence:** HIGH (mypy is the standard Python type checker)

### Linting & Formatting

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **ruff** | 0.6+ | Fast linter and formatter | **Replaces black + flake8 + isort**. 10-100x faster, written in Rust, compatible with black formatting, includes 700+ rules. Modern standard for 2025. |

**Migration path:** Replace black + flake8 with ruff. Already have black configured at 100 char line length, ruff can import those settings.

**Alternatives considered:**
- Keep black + flake8: Works but slower, two tools instead of one
- Use pylint: More opinionated, slower, overlapping rules with flake8

**Confidence:** MEDIUM (ruff is rapidly becoming standard but is relatively new, ~2023+)

### Logging

| Library | Purpose | Notes |
|---------|---------|-------|
| **logging** (stdlib) | Structured logging | Use standard library. Configure with `basicConfig()` for CLI. Module-level loggers with `logging.getLogger(__name__)`. **No third-party library needed.** |
| **rich** | Beautiful CLI output | Optional: Adds color, tables, progress bars to CLI output. Can integrate with logging via `RichHandler`. |

**Standard pattern for CLI tools:**
```python
import logging
logger = logging.getLogger(__name__)

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
```

**Confidence:** HIGH (verified with official Python 3.14 docs, stdlib logging is standard)

### Performance & Profiling

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| **pytest-benchmark** | 4.0+ | Microbenchmarks in tests | Regression testing for performance, compare before/after optimization. |
| **memory_profiler** | 0.61+ | Memory usage profiling | Profile memory leaks, memory-intensive operations. |
| **py-spy** | 0.3+ | Sampling profiler | Production-safe profiling, no code changes needed, visualize with flamegraphs. |

**Confidence:** MEDIUM (standard tools but versions based on training data)

### Security & Validation

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **bandit** | 1.7+ | Security linter | Detects security issues (hardcoded passwords, SQL injection, insecure requests). Essential for production. |
| **safety** | 3.0+ | Dependency vulnerability scanner | Checks dependencies against CVE database. Run in CI. |
| **pydantic** | 2.0+ | Data validation | Validate configuration, API responses. Type-safe, better than manual validation. |

**Confidence:** MEDIUM (bandit/safety are standard, pydantic 2.0 is well-adopted)

---

## Installation

### Core Testing Stack
```bash
# Testing framework
pip install pytest>=8.0 pytest-cov>=5.0 pytest-mock>=3.14 pytest-xdist>=3.5

# HTTP mocking
pip install responses>=0.25 vcrpy>=6.0

# Type checking
pip install mypy>=1.10 types-requests>=2.31
```

### Linting & Formatting
```bash
# Modern unified linter (replaces black + flake8)
pip install ruff>=0.6
```

### Logging Enhancement (Optional)
```bash
# Rich CLI output
pip install rich>=13.0
```

### Performance Tools
```bash
pip install pytest-benchmark>=4.0 memory-profiler>=0.61 py-spy>=0.3
```

### Security
```bash
pip install bandit>=1.7 safety>=3.0 pydantic>=2.0
```

### Consolidated Dev Dependencies
```toml
[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-mock>=3.14",
    "pytest-xdist>=3.5",
    "responses>=0.25",
    "vcrpy>=6.0",

    # Type checking
    "mypy>=1.10",
    "types-requests>=2.31",

    # Linting & formatting
    "ruff>=0.6",

    # Performance
    "pytest-benchmark>=4.0",
    "memory-profiler>=0.61",
    "py-spy>=0.3",

    # Security
    "bandit>=1.7",
    "safety>=3.0",

    # Data validation
    "pydantic>=2.0",

    # Optional: Rich CLI
    "rich>=13.0",
]
```

---

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| **Linting** | ruff | black + flake8 + isort | If team is conservative, established tools work fine |
| **HTTP Mocking** | responses | requests-mock | If prefer pytest fixture style over decorator style |
| **Type Checking** | mypy | pyright (Microsoft) | If using VS Code heavily, pyright is faster |
| **CLI Output** | rich (optional) | colorama | If only need basic color, colorama is lighter |
| **Data Validation** | pydantic | attrs + cattrs | If pydantic feels heavyweight, attrs is simpler |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **nose/nose2** | Deprecated, pytest is successor | pytest |
| **unittest** (as framework) | Verbose, less features than pytest | pytest (can still use unittest.mock) |
| **flake8 + black + isort** separately | Three tools, slower, more config | ruff (all-in-one) |
| **pylint** alone | Slow, overly opinionated, config-heavy | ruff |
| **Custom logging frameworks** (loguru, structlog) | Stdlib is sufficient for CLI tools, adds dependency | logging (stdlib) |
| **coverage.py** directly | Use via pytest-cov for better integration | pytest-cov |

---

## Configuration Recommendations

### pytest Configuration (pyproject.toml)

Current configuration is minimal. Enhance with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",                          # Verbose output
    "--strict-markers",            # Error on unknown markers
    "--cov=src/mc",               # Coverage for src/mc package
    "--cov-report=term-missing",   # Show missing lines
    "--cov-report=html",           # HTML coverage report
    "--cov-fail-under=80",        # Fail if coverage < 80%
    "-n=auto",                     # Auto-detect CPU count for xdist
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests (> 1 second)",
]
```

### mypy Configuration (pyproject.toml)

Current: `disallow_untyped_defs = false` (too permissive)

**Recommended progressive typing:**

```toml
[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_unreachable = true
strict_optional = true

# Progressive: Start false, enable per-module
disallow_untyped_defs = false
disallow_untyped_calls = false

# Per-module strict typing
[[tool.mypy.overrides]]
module = "mc.utils.*"
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "mc.config.*"
disallow_untyped_defs = true
```

**Migration strategy:** Enable `disallow_untyped_defs` per module as you add tests, not globally at start.

### ruff Configuration (pyproject.toml)

Replace black + flake8 sections with:

```toml
[tool.ruff]
line-length = 100
target-version = "py38"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "ARG",  # flake8-unused-arguments
    "SIM",  # flake8-simplify
]
ignore = [
    "E501",  # Line too long (handled by formatter)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["ARG", "S101"]  # Allow unused args, asserts in tests
```

### bandit Configuration (pyproject.toml)

```toml
[tool.bandit]
exclude_dirs = ["tests", "archive"]
skips = ["B101"]  # Allow assert in non-test code if needed
```

---

## Stack Patterns by Use Case

### Pattern 1: Unit Testing with HTTP Mocking

**When:** Testing functions that call external APIs

**Stack:**
- pytest + pytest-mock (for general mocking)
- responses (for requests library mocking)

**Example:**
```python
import responses
import requests

@responses.activate
def test_api_call():
    responses.add(
        responses.GET,
        'https://api.example.com/data',
        json={'key': 'value'},
        status=200
    )
    result = my_function_that_calls_api()
    assert result['key'] == 'value'
```

### Pattern 2: Integration Testing with Real APIs

**When:** Testing against real API endpoints (sparingly)

**Stack:**
- pytest
- vcrpy (record real responses once, replay in CI)

**Example:**
```python
import vcr

@vcr.use_cassette('fixtures/vcr_cassettes/api_call.yaml')
def test_real_api():
    result = my_function_that_calls_real_api()
    assert result['status'] == 'success'
```

### Pattern 3: Progressive Type Safety

**When:** Brownfield project, can't type everything at once

**Strategy:**
1. Add type stubs: `pip install types-requests`
2. Enable mypy warnings (not errors)
3. Add types to new code
4. Enable `disallow_untyped_defs` per module
5. Gradually cover entire codebase

### Pattern 4: CLI Logging Hierarchy

**When:** CLI tool with multiple modules

**Pattern:**
```python
# In each module
logger = logging.getLogger(__name__)

# In main CLI entry point
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # All module loggers automatically inherit this config
```

**With verbosity flag:**
```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='...')
```

---

## Version Compatibility

### Python Version Support

**Current:** Python 3.8+ (as specified in pyproject.toml)

**Compatibility notes:**
- pytest 8.0+ supports Python 3.8+
- mypy 1.10+ supports Python 3.8+
- ruff supports Python 3.7+
- pydantic 2.0+ requires Python 3.8+

**Recommendation:** Continue supporting Python 3.8+ until at least mid-2025 (Python 3.8 EOL is October 2024, but many enterprises lag).

### Known Incompatibilities

| If using... | Requires | Notes |
|-------------|----------|-------|
| pydantic 2.0+ | Python 3.8+ | Breaking changes from 1.x, migration guide exists |
| pytest-xdist | pytest 7.0+ | Already satisfied |
| responses 0.25+ | requests 2.22+ | Already satisfied (have 2.31+) |

---

## Migration Path from Current State

### Current State Analysis

**Existing pyproject.toml has:**
- pytest 7.0+ (outdated, current is 8.0+)
- pytest-cov 4.0+ (outdated, current is 5.0+)
- black 23.0+ (will replace with ruff)
- flake8 6.0+ (will replace with ruff)
- mypy 1.0+ (outdated, current is 1.10+)

### Recommended Migration Steps

1. **Update existing tools:**
   ```bash
   pip install --upgrade pytest pytest-cov mypy
   ```

2. **Add testing essentials:**
   ```bash
   pip install pytest-mock pytest-xdist responses vcrpy types-requests
   ```

3. **Replace black + flake8 with ruff:**
   ```bash
   pip install ruff
   pip uninstall black flake8  # Optional: can keep during transition
   ```

4. **Add security scanning:**
   ```bash
   pip install bandit safety
   ```

5. **Add optional enhancements:**
   ```bash
   pip install rich pydantic pytest-benchmark
   ```

6. **Update pyproject.toml** with enhanced configurations above

7. **Create first tests** using responses for HTTP mocking

---

## Testing Strategy Recommendations

### Test Organization (Already Structured)

Current structure is good:
```
tests/
├── __init__.py
├── unit/          # Fast, isolated tests
├── integration/   # Tests with external dependencies
└── fixtures/      # Shared test data, VCR cassettes
```

### Coverage Targets

| Phase | Target | Rationale |
|-------|--------|-----------|
| Phase 1: Foundation | 60% | Get core utils tested |
| Phase 2: Feature coverage | 75% | Cover main business logic |
| Phase 3: Production-ready | 85%+ | High confidence for deployment |

**Note:** Don't aim for 100% immediately. Focus on high-value code first.

### Test Pyramid

For CLI tools:

```
    /\
   /  \      E2E (5%): Full CLI invocation tests
  /____\     Integration (20%): API + CLI interaction tests
 /______\    Unit (75%): Pure function tests, mocked HTTP
```

---

## Performance Benchmarking Strategy

### When to Benchmark

1. **Before optimization:** Establish baseline with pytest-benchmark
2. **After optimization:** Verify improvement
3. **Regression testing:** CI runs benchmarks, fails if >10% slower

### Example Setup

```python
def test_parse_performance(benchmark):
    result = benchmark(parse_large_response, sample_data)
    assert result is not None
```

---

## Sources

**HIGH confidence (official documentation):**
- Python logging documentation (https://docs.python.org/3/library/logging.html) - Verified 2026-01-20, Python 3.14 docs

**MEDIUM confidence (training data from 2025, widely adopted):**
- pytest ecosystem (pytest, pytest-cov, pytest-mock, pytest-xdist)
- mypy type checking
- ruff linting (newer tool, rapidly becoming standard)
- responses/vcrpy for HTTP mocking
- bandit/safety for security scanning

**LOW confidence (version numbers based on training data):**
- Specific version numbers (8.0, 5.0, 1.10, etc.) - should be verified against PyPI
- pydantic 2.0 adoption timeline
- ruff adoption as standard replacement for black+flake8

**Recommendation:** Verify all version numbers against PyPI before finalizing dependency specifications.

---

*Stack research for: Python CLI Tool Hardening*
*Researched: 2026-01-20*
*Primary focus: Testing, type checking, linting, logging, and performance tools*

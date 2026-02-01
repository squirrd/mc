---
created: 2026-02-01T18:48
title: Validate case number format before credential/API checks
area: general
files:
  - src/mc/cli/commands/container.py:161-214
  - src/mc/terminal/attach.py:119-123
---

## Problem

Case number format validation happens too late in the execution flow. When users provide an invalid case number (e.g., `mc case 123` with only 3 digits instead of 8), the CLI checks Salesforce credentials first and produces a misleading error message.

**Current behavior:**
```bash
$ mc case 123
Error: Salesforce credentials not configured. Update config at /Users/dsquirre/Library/Application Support/mc/config.toml
```

**Expected behavior:**
```bash
$ mc case 123
Error: Invalid case number: 123. Must be 8 digits.
```

**Discovered during:** Test 7.1 (Invalid Case Number) in manual UAT testing

**Technical details:**

The execution flow in `case_terminal()` (container.py lines 161-214):
1. Loads config
2. **Checks Salesforce credentials (lines 175-190)** ← Happens first
3. Initializes SalesforceAPIClient
4. Calls `attach_terminal()` which **validates format (attach.py lines 119-123)** ← Happens too late

**Why this matters (fail-fast principle):**
- **Better UX**: Users get immediate, accurate feedback about their mistake
- **Faster failure**: No need to check credentials or initialize clients for invalid input
- **Clear error messages**: Users understand what's wrong without confusion
- **Avoid misleading errors**: Don't suggest credential problems when input is malformed
- **Security**: Don't expose credential check logic to attackers fuzzing with invalid input

## Solution

Move case number validation to the earliest possible point in all commands that accept case numbers.

**1. Create shared validation function** (if not already exists):
```python
# In src/mc/utils/validation.py or similar
def validate_case_number_format(case_number: str) -> None:
    """Validate case number is exactly 8 digits.

    Raises:
        ValueError: If case number format is invalid
    """
    if not case_number.isdigit() or len(case_number) != 8:
        raise ValueError(
            f"Invalid case number: {case_number}. Must be 8 digits."
        )
```

**2. Call validation early in case_terminal():**
```python
def case_terminal(args: argparse.Namespace) -> None:
    case_number = args.case_number

    # Validate FIRST, before any other operations
    try:
        validate_case_number_format(case_number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Now proceed with config, credentials, etc.
    config_manager = ConfigManager()
    # ... rest of function
```

**3. Apply to all entry points:**
- `case_terminal()` in container.py
- `quick_access()` in container.py (calls case_terminal, so covered)
- `create()`, `stop()`, `delete()`, `exec_command()` in container.py
- Any other commands accepting case numbers

**4. Remove duplicate validation:**
After adding early validation, the check at attach.py:119-123 becomes redundant (defensive depth is fine, but error should never reach there).

**Testing:**
- Verify all invalid formats fail fast with clear messages:
  - `mc case 123` (too short)
  - `mc case 123456789` (too long)
  - `mc case abcd1234` (non-digits)
  - `mc case ""` (empty)
- Verify valid format passes validation: `mc case 12345678`

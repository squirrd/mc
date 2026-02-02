# Claude Code Skills for MC Project

This directory contains custom Claude Code skills for the MC project.

## Available Skills

### `/fix-integration-tests`
**File:** `fix-integration-tests.md`

Automatically fix failing integration tests using parallel subagents.

**Features:**
- Runs full integration test suite
- Spawns parallel agents to analyze failures
- Creates separate git branches for each fix
- Verifies all fixes work together
- Optional GSD integration for complex scenarios

**Usage:**
```bash
/fix-integration-tests
```

**See:** `docs/skills/fix-integration-tests.md` for detailed documentation

---

### `/bug-to-test`
**File:** `bug-to-test.md`

Convert UAT failures or production bugs into automated integration tests.

**Features:**
- Guided investigation and root cause analysis
- Creates regression tests with real components
- Updates documentation (UAT docs, REGRESSION_TESTS.md)
- Emphasizes real integration (no mocks unless necessary)

**Usage:**
```bash
/bug-to-test <error message or description>
```

**See:** `docs/USING_BUG_TO_TEST.md` for project-specific guidance

---

## Installation

These skills are **optional** but recommended for test-driven development workflow.

### Option 1: Symlink (Recommended)

Create symlinks in your `.claude/commands/` directory:

```bash
# From the project root
cd /Users/dsquirre/Repos/mc

# Create symlinks
ln -s $(pwd)/.claude-skills/fix-integration-tests.md .claude/commands/fix-integration-tests.md
ln -s $(pwd)/.claude-skills/bug-to-test.md .claude/commands/bug-to-test.md
```

**Benefits:**
- Skills auto-update when project is pulled
- Share improvements with team
- Single source of truth

### Option 2: Copy (Simple)

Copy the skill files to your `.claude/commands/` directory:

```bash
cp .claude-skills/*.md .claude/commands/
```

**Note:** You'll need to manually update when skills change.

### Option 3: Include in .clinerules

If you want skills to be project-specific (not user-specific), add to `.clinerules`:

```markdown
# In .clinerules or project-specific config

Include skills from: .claude-skills/
```

(Check Claude Code documentation for current syntax)

---

## Verification

After installation, verify skills are loaded:

```bash
# In Claude Code
/skills

# Should show:
# - fix-integration-tests
# - bug-to-test
```

---

## Workflow Integration

### Test-Driven Development Workflow

1. **Run UAT Test Manually**
   ```bash
   # Follow steps from .planning/UAT-TESTS-BATCH-ABCE.md
   mc case 04347611
   ```

2. **Bug Found? Create Regression Test**
   ```bash
   /bug-to-test <error details>
   ```

3. **Fix All Integration Test Failures**
   ```bash
   /fix-integration-tests
   ```

4. **Verify Everything**
   ```bash
   uv run pytest -v --no-cov
   ```

### GSD Integration Workflow

For complex multi-bug scenarios:

```bash
# Use fix-integration-tests with GSD
/fix-integration-tests
# Choose "Use GSD phases" when prompted

# Creates phases for each fix
# Resume if interrupted:
/gsd:resume-work

# Verify phase completion:
/gsd:progress
```

---

## Best Practices

Both skills follow principles from:
- `docs/INTEGRATION_TEST_BEST_PRACTICES.md`
- `docs/USING_BUG_TO_TEST.md`

**Key Principle:** Use real components in integration tests
- ✅ Real API clients
- ✅ Real Podman
- ✅ Real databases
- ✅ Real file system (with tmp_path)
- ⚠️ Mock only TTY, time, external services

**Golden Rule:** If it can be real, make it real.

---

## Skill Development

### Contributing Improvements

1. Edit skill files in `.claude-skills/`
2. Test the skill in your local environment
3. Commit changes (this directory is NOT gitignored)
4. Share improvements with team

### Creating New Skills

See existing skills as templates:
- `fix-integration-tests.md` - Complex multi-phase skill with GSD integration
- `bug-to-test.md` - Interactive skill with user questions

**Skill file format:**
```markdown
---
name: skill-name
description: Brief description
argument-hint: "optional: hint text"
allowed-tools:
  - Read
  - Write
  - Task
---

<objective>
What this skill does
</objective>

<context>
@relevant/files
</context>

<process>
<step name="step_name">
Instructions...
</step>
</process>
```

---

## See Also

- `/skills` - List all available skills in Claude Code
- `docs/skills/` - Detailed skill documentation
- `.claude/commands/` - Your local skill directory (gitignored)

---

## Troubleshooting

**Skills not showing up?**
1. Check `.claude/commands/` directory exists
2. Verify files are .md format
3. Restart Claude Code
4. Run `/skills` to verify

**Skill errors?**
1. Check skill file YAML frontmatter is valid
2. Verify allowed-tools are correct
3. Check for syntax errors in process steps

**Need help?**
- See skill documentation in `docs/skills/`
- Check `docs/USING_BUG_TO_TEST.md` for examples
- Review existing skills for patterns

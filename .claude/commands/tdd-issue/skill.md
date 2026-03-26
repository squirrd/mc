---
name: tdd-issue
description: Fix a bug using TDD — red/green/refactor with parallel worktrees and issue tracking
argument-hint: "optional: shortFixName"
allowed-tools:
  - Read
  - Agent
  - AskUserQuestion
  - Bash
---

<configuration>
REPO_ROOT: /Users/dsquirre/Repos/mc
TRACKING_FILE: .tdd/issues/ISSUE_TRACKING.md
PHASES_DIR: .claude/commands/tdd-issue/phases
</configuration>

<objective>
Fix a bug using strict Red-Green-Refactor TDD discipline across 4 sequential phases.
Each phase runs as an isolated sub-agent that reads only the instructions and references it needs.
State is persisted in .tdd/issues/<shortFixName>/resume.md (main repo, gitignored).
</objective>

<process>

## 1. Bootstrap

```bash
cd /Users/dsquirre/Repos/mc && bash .claude/commands/tdd-issue/scripts/bootstrap.sh
```

## 2. Resume detection

Read `/Users/dsquirre/Repos/mc/.tdd/issues/ISSUE_TRACKING.md` (if it exists).
Find all issues with `Status | IN_PROGRESS`.

**If 0 IN_PROGRESS issues:** proceed to phase dispatch with `start_phase = setup`.

**If 1 IN_PROGRESS issue:** Use AskUserQuestion:
```
Found in-progress issue fix/<name> — <description>.
Resume it, or start a new issue? [resume / new]
```
- `resume` → read `/Users/dsquirre/Repos/mc/.tdd/issues/<name>/resume.md`, set `shortFixName = <name>`, set `start_phase` from `current_phase` field in resume.md
- `new` → `start_phase = setup`

**If N > 1 IN_PROGRESS issues:** Use AskUserQuestion listing all issues with their descriptions and
last-updated timestamps. Ask user to enter the issue number or `new`.
On selection → read that issue's resume.md and set `start_phase` from `current_phase`.

## 3. Phase dispatch

Spawn phase agents sequentially using the Agent tool (foreground — wait for each before spawning next).
Start from `start_phase`. Skip phases before `start_phase` when resuming.

Pass `resume_context` to each phase agent: the full text of resume.md if resuming, otherwise `""`.

### Phase order

**setup** (Detective — STEP 0a/0b/0d, 1, 2):
```
Agent(
  subagent_type="general-purpose",
  description="tdd-issue setup phase: Detective",
  prompt="""
Read and follow ALL instructions at:
  /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/phases/setup.md

Variables:
  repo_root: /Users/dsquirre/Repos/mc
  resume_context: <resume.md contents or empty string>
"""
)
```

Collect JSON result. On `status=BLOCKED` → display `details` and stop.

**red** (Prosecutor — STEP 3, 4, 4.3, 4.5, 5):
```
Agent(
  subagent_type="general-purpose",
  description="tdd-issue red phase: Prosecutor",
  prompt="""
Read and follow ALL instructions at:
  /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/phases/red.md

Variables:
  repo_root:    /Users/dsquirre/Repos/mc
  shortFixName: <from setup result>
  bugClass:     <from setup result>
  reproSummary: <from setup result>
  errorMessage: <from setup result>
  severity:     <from setup result>
  source:       <from setup result>
  resume_context: <resume.md contents or empty string>
"""
)
```

On `status=CANCELLED` → display details and stop.
On `status=BLOCKED` → display details and stop.

**green** (Surgeon — STEP 6, 7, 8, 9, 10):
```
Agent(
  subagent_type="general-purpose",
  description="tdd-issue green phase: Surgeon",
  prompt="""
Read and follow ALL instructions at:
  /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/phases/green.md

Variables:
  repo_root:               /Users/dsquirre/Repos/mc
  shortFixName:            <from setup result>
  bugClass:                <from setup result>
  reproSummary:            <from setup result>
  integrationTestFile:     <from red result>
  integrationTestFunction: <from red result>
  resume_context: <resume.md contents or empty string>
"""
)
```

On `status=BLOCKED` → display details and stop.

**close** (Inspector — STEP 11):
```
Agent(
  subagent_type="general-purpose",
  description="tdd-issue close phase: Inspector",
  prompt="""
Read and follow ALL instructions at:
  /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/phases/close.md

Variables:
  repo_root:               /Users/dsquirre/Repos/mc
  shortFixName:            <from setup result>
  integrationTestFile:     <from red result>
  integrationTestFunction: <from red result>
  unitTestsFixed:          <from green result>
"""
)
```

On `status=BLOCKED` → display details and stop.

## 4. Final output

Display the close phase's summary output to the user.

</process>

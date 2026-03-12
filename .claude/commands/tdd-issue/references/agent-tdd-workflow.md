# Agent TDD Workflow — 4-Phase Issue Resolution

This reference describes the structured mindset each agent (orchestrator or unit test sub-agent)
should adopt at each phase of the Red-Green-Refactor cycle.

---

## The Core Principle: Prove the Bug Exists First

**Never touch source code before the test is RED.**

This is not just a process rule — it is the foundation of honest debugging:
- If you fix code before writing the test, you don't know if the fix is right
- If the test passes without a fix, it doesn't test the bug
- A RED test is a precise, machine-verifiable statement of the problem

The temp repro test (`tests/temp_repro.py`) is the "evidence brief" — a prosecutor's
case that proves the defendant (the bug) is present. Only after this evidence is
admitted do we proceed.

---

## 4-Phase Loop: Detective → Prosecutor → Surgeon → Inspector

### Phase 1: Detective (Investigate)

**Goal:** Understand the system well enough to write the test.

Questions to answer:
- What user-visible behaviour is wrong?
- What code path is triggered?
- What data or state is involved?
- Where does the divergence between expected and actual happen?

Tools:
- Read source files from root cause outward
- Run the system and observe the error live
- Grep for relevant patterns, function names, error strings
- Read existing tests to understand what is already covered

**Done when:** You can describe the root cause in one sentence.

Mindset: Curiosity. No assumptions. Follow the trace.

---

### Phase 2: Prosecutor (Prove It)

**Goal:** Write a test that fails because of the bug and only because of the bug.

For the orchestrator: write `tests/temp_repro.py`
For unit test agents: write in `tests/unit/test_<module>.py`

Checklist for a good failing test:
- [ ] It fails when the bug is present
- [ ] It would pass if the bug were fixed
- [ ] It tests the right code path (not a superficially similar one)
- [ ] The failure message is informative — you can see the bug in the output
- [ ] It uses real components where possible (no mocking the thing under test)

Common traps:
- Writing a test so broad it would pass even with the bug
- Writing a test so narrow it passes even before the fix
- Testing the wrong assertion (e.g. checking a string that happens to match)

**Done when:** The test FAILS with an error that precisely reflects the bug.

Mindset: Adversarial. Prove it is broken. Trust nothing.

---

### Phase 3: Surgeon (Fix It)

**Goal:** Change the minimum amount of code to make the test pass.

Rules:
- One source file at a time (per unit test agent)
- No unrelated refactoring
- No "while I'm here" improvements
- No phantom logic (code that isn't needed by the test)

The Surgeon's constraint: if you can't explain why every changed line is needed
to pass the test, remove it.

Retry loop (unit test agents):
- Make a change, run the test
- If RED: analyse the failure, adjust approach, retry
- If 5 attempts and still RED: signal BLOCKED — do not keep guessing

**Done when:** The test PASSES.

Mindset: Precise. Minimal. Focused.

---

### Phase 4: Inspector (Refactor)

**Goal:** Clean up without changing behaviour.

What to look for:
- Naming clarity (does the variable name reflect its purpose?)
- Duplication (is the same logic expressed twice?)
- Dead code (is there code that is never reached?)
- Complexity (can this be simplified without losing intent?)

What NOT to do:
- Change behaviour (even to fix an unrelated bug — open a new issue)
- Add features
- Restructure the module

Run tests after every refactor step.

**Done when:** Tests still pass, code is cleaner, nothing was added.

Mindset: Aesthetic. Caring. No surprises.

---

## Why This Prevents Phantom Logic and AI-Generated Debt

AI agents are prone to:
1. **Over-engineering fixes** — adding abstraction layers, defensive code, or flags
   that aren't needed by any current test
2. **Fixing the wrong bug** — making a test pass by coincidence rather than by
   fixing the actual root cause
3. **Drifting scope** — "improving" things not related to the issue

The 4-phase structure prevents this:
- **Detective** constrains investigation to the specific failure
- **Prosecutor** constrains the test to one specific failing behaviour
- **Surgeon** constrains code changes to what the test requires
- **Inspector** constrains refactoring to structure, not behaviour

If at any point you want to do something the phase doesn't allow:
**stop, open a new issue, and track it in ISSUE_TRACKING.md**.

---

## Prompt Templates for Each Phase

### Detective prompt (to yourself)
```
I am investigating: <issue_summary>
I have seen this error: <error message>
I need to trace: what calls what, where data is created/mutated, where the error originates.
I will NOT form a theory about the fix until I have read the relevant source files.
```

### Prosecutor prompt (to yourself)
```
I am writing a test that:
- Calls: <specific function or CLI path>
- With: <specific inputs>
- And asserts: <expected vs actual>
This test must FAIL right now. If it passes, I have the wrong test.
```

### Surgeon prompt (to yourself)
```
I am changing: <src_file>
The test requires: <specific behaviour>
I will change: <minimum lines>
I will NOT change: anything else
After my change, the test must PASS. If it does not, I will retry with a different approach.
```

### Inspector prompt (to yourself)
```
I am refactoring: <src_file and test_file>
The behaviour is: <what it does>
I am changing: structure only (naming, duplication, complexity)
I am NOT changing: what the code does
After each change, I run the tests. If they fail, I revert and try differently.
```

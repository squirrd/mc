# UAT Test System — mc & mc-update

Manual User Acceptance Testing suite for the `mc` CLI and `mc-update` tools.

---

## Structure

```
tests/uat/
├── README.md               # This file
├── STATUS.md               # Dashboard — last sprint per feature, pass rate
├── features/               # Test library — grows indefinitely, never deleted
│   ├── ver.md              # VER-*  : mc version
│   ├── upd.md              # UCHK-*, UUPG-*, UPIN-*, UUPN-*  : mc-update
│   ├── att.md              # ATT-*  : mc attachments
│   ├── chk.md              # CHK-*  : mc check
│   ├── new.md              # NEW-*  : mc create
│   ├── cmt.md              # CMT-*  : mc comments
│   ├── cs.md               # CS-*   : mc case
│   ├── who.md              # WHO-*  : mc ldap
│   ├── url.md              # URL-*  : mc launch
│   └── agt.md              # AGT-*  : mc agent
├── runs/
│   ├── pending/            # Sprints ready to execute (created by /uat-sprint)
│   │   └── YYYY-MM-DD.md
│   └── completed/          # Archived sprints with results (moved by /uat-process-sprint)
│       └── YYYY-MM-DD.md
└── data/
    ├── feature_map.json    # Feature → source file mapping (used by scripts)
    ├── tc_history.json     # TC run history — managed by process_sprint.py
    └── feature_meta.json   # Last codebase review per feature — managed by uat-review skill
```

---

## TC ID Convention

Every test case has a globally unique ID using a feature prefix:

| Feature | Binary | Prefix |
|---|---|---|
| `mc version` | mc | VER |
| `mc attachments` | mc | ATT |
| `mc check` | mc | CHK |
| `mc create` | mc | NEW |
| `mc comments` | mc | CMT |
| `mc case` | mc | CS |
| `mc ldap` | mc | WHO |
| `mc launch` | mc | URL |
| `mc agent` | mc | AGT |
| `mc-update check` | mc-update | UCHK |
| `mc-update upgrade` | mc-update | UUPG |
| `mc-update pin` | mc-update | UPIN |
| `mc-update unpin` | mc-update | UUPN |

IDs are sequential within a prefix: `VER-01`, `VER-02`, `UPIN-03`, etc.

---

## TC Header Format

Each TC in a feature file uses this header to enable sprint automation:

```markdown
### TC-PREFIX-NN: Short description

**Pre-requires:** TC-XXXX-NN (reason) — or `none`
**Cross-deps:** TC-XXXX-NN (reason) — or `none`
**Tags:** tag1, tag2, tag3
```

- **Pre-requires** — TCs that must have run (and passed) in the same sprint *before* this TC. The sprint builder automatically includes pre-required TCs.
- **Cross-deps** — TCs from *another feature* that must have run first. Cross-feature dependencies.
- **Tags** — used by the sprint builder for time estimation and filtering. Common tags:
  - `happy-path`, `negative`, `edge-case`, `validation`
  - `fast` (estimated 2 min), `network` (estimated 5 min), `mode: agent` (estimated 7 min)
  - `mode: host`, `mode: agent`, `mode: host+agent`
  - `streaming`, `config`, `browser`

---

## Result Checkboxes

When running a sprint, mark exactly **one** box per TC:

```markdown
**Result:**
- [x] PASS
- [ ] FAIL
- [ ] BLOCKED
```

Add tester notes below — required for FAIL and BLOCKED:

```markdown
**Notes:** uv install threw permission error on M2 Mac — likely SIP issue
```

---

## Workflow

### 1. Review test coverage for a feature

```
/uat-review cmt                              # Review mc comments coverage
/uat-review att chk new                      # Review multiple features
/uat-review upd "pin behavior after reinstall"   # With specific focus area
```

Analyzes source code + git commits since last review. Proposes new/improved TCs (up to 5 per feature). Writes approved TCs to feature files and updates `feature_meta.json`.

### 2. Build a sprint

```
/uat-sprint                       # All features — scores and selects TCs
/uat-sprint ver upd               # Target specific features only
/uat-sprint --minutes 30          # Cap sprint at ~30 minutes
/uat-sprint --max 10              # Cap at 10 TCs
/uat-sprint --minutes 45 --max 20 # Both caps (whichever hits first)
```

**Scoring priority (highest first):**

| Priority | Score | Condition |
|---|---|---|
| 1 | 200 | Never run (no history) |
| 2 | 150 | Last result was FAIL or BLOCKED |
| 3 | +75 | Source code changed since last sprint (additive) |
| 4 | 50 | Overdue regression (>30 days since last PASS, oldest first) |

**Time estimation from tags:**

| Tag | Estimated time |
|---|---|
| `fast` | 2 min |
| `network` | 5 min |
| `mode: agent` | 7 min |
| *(default)* | 3 min |

Sprint plan saved to `runs/pending/YYYY-MM-DD.md` with estimated total time.

### 3. Run the sprint

Open `runs/pending/YYYY-MM-DD.md`. For each TC:
1. Read the steps (open the feature file referenced)
2. Run on your machine (or in a container for agent-mode TCs)
3. Mark `[x] PASS`, `[x] FAIL`, or `[x] BLOCKED`
4. Add notes if not PASS

### 4. Process results

```
/uat-process-sprint              # Process pending sprint
/uat-process-sprint 2026-04-21   # Process specific sprint date
```

If multiple pending sprints exist, you'll be asked which one to process.

This will:
1. Parse all checkboxes from the sprint file
2. Create Jira Bug tickets for FAIL/BLOCKED TCs (project: MC, via `jira` CLI)
3. Update `data/tc_history.json` with results
4. Update `STATUS.md` dashboard
5. Move the sprint file from `runs/pending/` to `runs/completed/`

**Jira integration:** Uses `/opt/homebrew/bin/jira` with API token from macOS Keychain (`jira_p_api_token`). Falls back to a text summary if the CLI or token is unavailable.

### 5. Generate sprint report (optional)

```
/uat-build-sprint-report         # Prose summary of most recent completed sprint
/uat-build-sprint-report 2026-04-21  # Specific sprint
```

Writes a QA report to `runs/completed/YYYY-MM-DD-report.md` with pass/fail analysis, risk assessment, and recommended follow-up actions.

---

## Scripts

All scripts in `scripts/uat/` are standalone Python 3 and called by the skills above:

| Script | Purpose |
|---|---|
| `parse_features.py` | Extract all TC metadata from feature files + history |
| `analyze_git.py` | Map git commits to features by source path |
| `build_sprint.py` | Score and select TCs, output sprint plan markdown |
| `process_sprint.py` | Parse results, create Jira tickets, update history |

---

## Data Files

| File | Managed by | Purpose |
|---|---|---|
| `data/feature_map.json` | Manual | Maps features to source paths, prefixes, modes, aliases |
| `data/tc_history.json` | `process_sprint.py` | Per-TC run history (dates, results, notes, run counts) |
| `data/feature_meta.json` | `/uat-review` skill | Tracks last codebase review date/commit per feature |

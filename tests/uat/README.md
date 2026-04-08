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
- **Tags** — used by the sprint builder to score relevance. Common tags: `happy-path`, `negative`, `offline`, `network`, `config`, `fast`, `streaming`, `validation`.

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

### Build a sprint
```
/uat-sprint                  # All features with changes or due for regression
/uat-sprint upd ver          # Target specific features only
```
The script scores TCs by: last-failed (highest) → never-run → overdue regression → recent git changes.
Sprint plan saved to `runs/pending/YYYY-MM-DD.md`.

### Run the sprint
Open `runs/pending/YYYY-MM-DD.md`. For each TC:
1. Read the steps (open the feature file referenced)
2. Run on your machine
3. Mark `[x] PASS`, `[x] FAIL`, or `[x] BLOCKED`
4. Add notes if not PASS

### Process results
```
/uat-process-sprint          # Process most recent pending sprint
```
This will:
1. Parse all checkboxes
2. Print failed TCs in Jira-format (for bug filing)
3. Update `data/tc_history.json` and `STATUS.md`
4. Move the sprint file from `runs/pending/` to `runs/completed/`

### Add/improve tests for a feature
```
/uat-review upd                              # Review mc-update coverage
/uat-review upd "pin behavior after reinstall"   # With specific focus
```
Analyzes source code + git commits since last review. Proposes new/improved TCs.

### Generate sprint report
```
/uat-build-sprint-report     # Prose summary of most recent completed sprint
```

---

## Scripts

All scripts in `scripts/uat/` are standalone Python 3 and called by the skills above:

| Script | Purpose |
|---|---|
| `parse_features.py` | Extract all TC metadata from feature files + history |
| `analyze_git.py` | Map git commits to features by source path |
| `build_sprint.py` | Score and select TCs, output sprint plan markdown |
| `process_sprint.py` | Parse results, update history, output Jira failures |

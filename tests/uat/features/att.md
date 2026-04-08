# UAT Feature: `mc attachments` (ATT)

**Command:** `mc attachments <case>` / `mc att <case>`
**Source:** `src/mc/cli/commands/case.py`, `src/mc/utils/downloads.py`, `src/mc/integrations/redhat.py`
**Prefix:** ATT

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Network available (unless test specifies offline)
- Valid Red Hat case number with attachments

> **Status:** No TCs yet. Use `/uat-review att` to generate initial test suite.

---

## Coverage Map

| Behavior | TC |
|---|---|
| *(none yet)* | — |

# UAT Feature: `mc create` (NEW)

**Command:** `mc create <case>` / `mc new <case>`
**Source:** `src/mc/cli/commands/container.py`, `src/mc/cli/commands/case.py`, `src/mc/container/manager.py`, `src/mc/integrations/podman.py`
**Prefix:** NEW

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Podman running
- Network available (unless test specifies offline)
- Valid Red Hat case number

> **Status:** No TCs yet. Use `/uat-review new` to generate initial test suite.

---

## Coverage Map

| Behavior | TC |
|---|---|
| *(none yet)* | — |

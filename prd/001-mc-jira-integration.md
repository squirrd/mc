# PRD 001: Jira Integration — `mc jira` Command and Case-Ticket Linking

**Jira:** MC-16
**Status:** Ready for Agent
**Date:** 2026-05-26

---

## Problem Statement

MC CLI currently only supports Salesforce (SFDC) Cases as the entry point for Investigations. Support engineers frequently work on Jira Tickets (e.g., OHSS project) that may or may not be linked to SFDC Cases. Today, Jira data is manually exported and placed into ad-hoc directory structures (`000_Jira-Only/`). There is no programmatic integration, no automated discovery of Case-Ticket relationships, and no way to launch a containerized workspace from a Jira Ticket. This means the Investigator (AI agent inside the container) lacks Jira context unless the engineer manually provisions it.

## Solution

Add Jira as a first-class data source in MC CLI:

1. **New `mc jira <ticket-id>` command** — mirrors `mc case <case-number>`. Fetches Jira ticket data via `jr`, discovers linked SFDC Cases, scaffolds a Ticket Workspace, creates a container, and launches a terminal.
2. **Enhance `mc case <case-number>`** — after fetching SFDC metadata, discover linked Jira Tickets, pull their data into Ticket Workspaces under `~/mc/jira/`, and record the relationships in SQLite.
3. **Peer directory structure** — all Jira data lives under `~/mc/jira/{ticket-id}/`, never nested inside Case Workspaces. A SQLite `case_ticket_links` table tracks the many-to-many relationship between Cases and Tickets (see ADR 0001).

## User Stories

1. As a support engineer, I want to run `mc jira OHSS-52338` and get a containerized workspace with the Jira ticket data, so that I can investigate the issue with full tooling (backplane, ocm, cluster access).
2. As a support engineer, I want `mc jira OHSS-52338` to automatically discover linked SFDC Cases from the ticket's `SFDC Cases Links` field, so that I don't have to manually look up case numbers.
3. As a support engineer, I want `mc jira OHSS-52338` with a linked Case to create the Case Workspace (under `~/mc/cases/`) AND the Ticket Workspace (under `~/mc/jira/`), so that both sets of artifacts are available to the Investigator.
4. As a support engineer, I want `mc jira OHSS-52338` with no linked Case to create a standalone Ticket Workspace under `~/mc/jira/OHSS-52338/`, so that I can work Jira-only Investigations.
5. As a support engineer, I want `mc case 04416520` to automatically discover linked Jira Tickets from the SFDC metadata, fetch their data via `jr`, and store them under `~/mc/jira/`, so that the Investigator has full context without manual data gathering.
6. As a support engineer, I want the many-to-many relationship between Cases and Tickets tracked in SQLite, so that `mc` can navigate between related Investigations in both directions.
7. As a support engineer, I want to type ticket IDs in lowercase (e.g., `ohss-52338`) and have them auto-uppercased, so that I don't have to worry about case sensitivity.
8. As a support engineer, I want ticket IDs from any Jira project (not just OHSS) to be accepted, so that the tool works if I encounter tickets in other Red Hat Jira projects.
9. As a support engineer, I want `mc jira` to use the work Jira profile (`~/.config/jira/w/config.yml`), so that authentication to the Red Hat Jira is handled via `jr`'s existing Keychain-backed auth.
10. As a support engineer, I want the Ticket Workspace to contain the raw ticket JSON and note files (`notes-01.md`, `notes-02.md`, `notes-03.md`, `tmp.md`), so that the Investigator has machine-readable ticket data and I have space for notes.
11. As a support engineer, I want `mc jira OHSS-52338` to create a container named `mc-OHSS-52338` and launch a terminal with prompt `[MC-OHSS-52338]`, so that the experience mirrors `mc case`.
12. As a support engineer, I want the `~/mc/jira/` directory created lazily on first use, so that it doesn't clutter the filesystem for users who don't use Jira.
13. As a support engineer, I want to manually link a Ticket to a Case using `mc jira OHSS-52338 --link 04416520`, so that I can establish relationships that aren't automatically discoverable.
14. As a support engineer, I want Case Workspaces to no longer contain `jira/` and `jira/atts/` subdirectories, since Jira data now lives in the peer `~/mc/jira/` directory structure.
15. As an Investigator (AI agent), I want Jira ticket data in JSON format in the Workspace, so that I can parse it programmatically to inform my investigation.
16. As an Investigator (AI agent), I want to discover related Cases for a Ticket (and vice versa) via the SQLite `case_ticket_links` table, so that I can cross-reference artifacts across related Investigations.
17. As a support engineer, I want `mc jira` with a linked Case that has multiple SFDC cases to show me which cases are linked, so that I understand the scope of the Investigation.
18. As a support engineer, I want the Jira-only workspace (`~/mc/jira/OHSS-52338/`) to remain in place if a Case gets linked later, so that my existing notes and artifacts are not disrupted.

## Implementation Decisions

### Modules

1. **Ticket ID Validator** — new `validate_ticket_id()` function, peer to `validate_case_number()`. Validates format `^[A-Z]{1,10}-\d+$`, normalizes lowercase input to uppercase.

2. **JiraClient** — new integration module wrapping the `jr` CLI. Shells out to `jr issue view <ticket-id> --raw -c <config-path>`, parses JSON response. Provides two key methods: fetch a ticket's full data, and extract linked SFDC case numbers from the `SFDC Cases Links` custom field. The exact custom field key (`customfield_NNNNN`) will be discovered during work profile setup by inspecting `jr --raw` output for an OHSS ticket. Fallback: regex scan comments for 8-digit case numbers matching the pattern from automated Jira comments.

3. **TicketWorkspaceManager** — new workspace manager for Ticket Workspaces. Scaffolds `~/mc/jira/{ticket-id}/` with: `{ticket-id}.json` (raw `jr` output), `notes-01.md`, `notes-02.md`, `notes-03.md`, `tmp.md`. Creates `~/mc/jira/` lazily on first use.

4. **StateDatabase migration** — add `case_ticket_links` table to `containers.db`:
   ```sql
   CREATE TABLE IF NOT EXISTS case_ticket_links (
       case_number TEXT NOT NULL,
       ticket_id TEXT NOT NULL,
       PRIMARY KEY (case_number, ticket_id)
   )
   ```
   Add CRUD methods: `add_link(case_number, ticket_id)`, `get_tickets_for_case(case_number)`, `get_cases_for_ticket(ticket_id)`, `remove_link(case_number, ticket_id)`.

5. **`mc jira` CLI entry point** — new subcommand in the CLI parser with alias. New `cli/commands/jira.py` command module. Orchestration flow:
   - Validate ticket ID
   - Fetch ticket data via JiraClient
   - Extract linked SFDC case numbers
   - If linked case(s): for each, trigger the existing Case workspace + container flow, record link in SQLite
   - If no linked case: create standalone Ticket Workspace, create container keyed on ticket ID, launch terminal
   - Optional `--link <case-number>` flag for manual association

6. **`mc case` enhancement** — after fetching SFDC metadata in the `attach_terminal` flow, check for linked Jira ticket IDs in the SFDC response. For each linked ticket: fetch via JiraClient, scaffold Ticket Workspace under `~/mc/jira/`, record link in SQLite.

7. **WorkspaceManager cleanup** — remove `jira/` and `jira/atts/` entries from `_generate_file_dir_list()`. Jira data no longer lives inside Case Workspaces per ADR 0001.

8. **`jr` work profile** — configuration prerequisite. Create `~/.config/jira/w/config.yml` for the Red Hat Jira instance (`redhat.atlassian.net`). Add `jira.config_path` to MC's `config.toml` to store the path to this profile.

### Container Identity

The existing container stack (`ContainerManager`, `StateDatabase`, `WindowRegistry`) accepts the identifier as a string and is not changed structurally. The `case_number` column in `containers` table stores either an 8-digit case number or a ticket ID like `OHSS-52338` — the column name is a misnomer for ticket-based containers but renaming requires a migration for zero functional benefit. Container names follow `mc-{identifier}` (e.g., `mc-OHSS-52338`). The prompt/bashrc follows `[MC-OHSS-52338]`.

### Jira Environment

MC only uses the **work** Jira profile (`~/.config/jira/w/`), which points to `redhat.atlassian.net`. The personal Jira profile (`~/.config/jira/p/`) is for MC project development tracking and is never used by the `mc` CLI itself. `jr` handles authentication via macOS Keychain.

### Case-Ticket Relationship Discovery

- **Jira → SFDC (primary):** Parse the `SFDC Cases Links` custom field from the `jr --raw` JSON output. This is a structured field visible in the Jira UI under the SFDC tab.
- **Jira → SFDC (fallback):** Regex scan ticket comments for 8-digit case numbers in automated link messages (e.g., `"case link for case: \d{8}"`).
- **Jira → SFDC (manual):** `--link <case-number>` flag on `mc jira` for user-provided associations.
- **SFDC → Jira:** Parse linked Jira ticket IDs from the Red Hat API case response. The SFDC API includes linked ticket references.

### Domain Language

Per CONTEXT.md: **Investigation** is the umbrella concept (domain only, not a code type). **Case** and **Ticket** are distinct code concepts with separate validators, clients, and workspace managers. **Investigator** is the primary AI agent consuming these artifacts. **Workspace** artifacts are optimized for machine readability.

## Testing Decisions

### What makes a good test

Tests should verify external behavior through the module's public interface, not implementation details. A good test for `JiraClient` asserts that given specific `jr` CLI output, the correct ticket data and linked case numbers are returned — it does NOT assert which subprocess flags were used. Tests should be resilient to refactoring of internals.

### Modules to test

1. **`validate_ticket_id`** — unit tests for valid IDs, lowercase normalization, rejection of invalid formats (no hyphen, digits-only, empty string, too-long prefix). Pattern after existing `validate_case_number` tests.

2. **JiraClient** — unit tests mocking `subprocess.run` to simulate `jr` CLI output. Test: successful ticket fetch with parsed JSON, extraction of linked case numbers from custom field, fallback to comment parsing, handling of `jr` errors (non-zero exit, invalid JSON, missing config). Integration test: real `jr` call against work profile (marked `@pytest.mark.integration`).

3. **TicketWorkspaceManager** — unit tests for directory scaffolding. Test: creates correct directory structure, creates note files, writes ticket JSON, handles pre-existing workspace (idempotent), lazy creation of `~/mc/jira/`. Pattern after existing `WorkspaceManager` tests.

4. **StateDatabase `case_ticket_links`** — unit tests for the migration and CRUD methods. Test: add link, get tickets for case, get cases for ticket, remove link, duplicate link handling (idempotent), empty results. Pattern after existing `StateDatabase` tests.

5. **`mc jira` CLI entry point** — integration tests for the full orchestration flow. Test: Jira-only ticket creates standalone workspace + container, ticket with linked case creates both workspaces + records link, `--link` flag creates manual association, invalid ticket ID shows error. Pattern after existing CLI command tests.

### Prior art

- `tests/unit/test_validation.py` — `validate_case_number` tests (pattern for ticket ID validator)
- `tests/unit/test_container_manager_create.py` — container creation tests (pattern for container keyed on ticket ID)
- `tests/unit/test_workspace_manager.py` — workspace scaffolding tests (pattern for TicketWorkspaceManager)
- `tests/integration/` — integration tests requiring Podman (pattern for `mc jira` end-to-end)

## Out of Scope

- **Migration of existing `000_Jira-Only/` data** — existing manually-created Jira workspaces in the backup are not auto-migrated to the new `~/mc/jira/` structure.
- **Automatic migration when a standalone Ticket later gets linked to a Case** — both workspaces stay where they are; the SQLite link is sufficient.
- **Container stack refactor** — no renaming of `case_number` columns, no polymorphic `Investigation` type in code. The existing string-based key system is widened to accept ticket IDs.
- **`mc container create <ticket-id>`** — the low-level `container create` subcommand is not modified in this PRD. Container creation for tickets flows through `mc jira` only.
- **Jira write operations** — `mc` only reads from Jira; it does not create tickets, add comments, or update fields.
- **Red Hat Jira profile (`~/.config/jira/w/`) setup automation** — the `jr init` process for the work profile is a manual prerequisite, not automated by `mc`.
- **Multiple Jira environments** — `mc` only uses the single work profile. No prefix-to-profile routing.

## Further Notes

- The `jr` CLI (`jira-cli`) supports `--raw` for JSON output, which is the parseable format used for all Jira data fetching. The exact custom field key for `SFDC Cases Links` needs to be discovered by inspecting `jr issue view <OHSS-ticket> --raw` output once the work profile is configured.
- The `~/mc/jira/` directory sits alongside `~/mc/cases/` under the configured `base_directory`. If the user has changed `base_directory` in `config.toml`, the jira directory follows.
- Container naming for tickets (`mc-OHSS-52338`) uses the full ticket ID including the hyphen. Podman container names allow hyphens, so this works without escaping.
- When `mc jira` finds multiple linked SFDC cases, it should display all of them and let the existing Case flow handle each one. The container and terminal are created for the primary entry point (the ticket), not for each linked case.

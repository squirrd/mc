# Jira ticket data lives in a peer directory, not nested under case workspaces

Jira ticket data lives under `~/mc/jira/{ticket-id}/` as a peer to `~/mc/cases/`, rather than nested inside each case workspace at `cases/{account}/{case}/jira/`. A SQLite `case_ticket_links` table in `containers.db` tracks the many-to-many relationship between cases and tickets.

We chose this because cases and Jira tickets have a many-to-many relationship — a single ticket can span multiple cases across different customers. Nesting Jira data inside case workspaces would require duplicating it into every linked case, creating a sync problem. The peer structure keeps one canonical copy of each ticket's data and uses the database to connect them. This also supports two entry points into mc (`mc case` and `mc jira`) without one being subordinate to the other.

## Considered Options

- **Nest Jira under cases** (`cases/{account}/{case}/jira/{ticket}/`): simpler, each workspace is self-contained. Rejected because duplication across linked cases creates staleness, and Jira-only investigations (no linked case) need a separate `000_Jira-Only/` convention.
- **Symlinks between peer directories**: avoids duplication while keeping both views. Rejected because hard links don't work for directories on APFS/ext4, and symlinks break on rename/move and confuse tools like `find` and `rsync`.
- **Reference files**: portable pointers between directories. Rejected because they require tooling to resolve — not navigable without mc or an AI agent.

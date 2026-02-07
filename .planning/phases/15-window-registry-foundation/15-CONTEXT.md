# Phase 15: Window Registry Foundation - Context

**Gathered:** 2026-02-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Persistent window ID storage with concurrent access support. This registry stores mappings between case numbers and terminal window IDs, enabling the terminal automation system to track which windows belong to which cases. The registry must handle concurrent access from multiple mc processes and automatically clean up stale entries when windows are closed.

</domain>

<decisions>
## Implementation Decisions

### Registry schema design
- **Full metadata storage**: Store case_number, window_id, created_at, terminal_type, container_id, process_id, and last_validated timestamp
- **One window per case**: case_number is the primary key - enforces 1:1 mapping between cases and windows
- **Separate database file**: Create dedicated window.db file rather than adding table to existing state.db - clean separation of concerns
- **TEXT window_id type**: Store window IDs as text strings to support both numeric (macOS) and alphanumeric (Linux) identifiers

### Concurrent access patterns
- **SQLite WAL mode**: Use Write-Ahead Logging for concurrent reads with single writer coordination
- **First write wins**: Use UNIQUE constraint on case_number - database rejects duplicate registrations, first process succeeds
- **Retry with exponential backoff**: On database lock timeout, retry 3-5 times with increasing delays (100ms, 200ms, 400ms)
- **Auto-commit per operation**: Each register/lookup/remove is its own transaction - simple, immediately durable, no transaction management needed

### Stale entry detection
- **Validate on lookup**: Check if window still exists when looking up window ID - lazy validation, no background work
- **Auto-remove stale entries**: When validation finds window no longer exists, delete the entry immediately and return None - self-healing behavior
- **Trigger new window creation**: After removing stale entry, the calling code should create a new window for the case
- **No validation tracking**: Always validate on every lookup - simpler logic, always accurate

### API surface & operations
- **Minimal CRUD operations**:
  - `register(case_number, window_id, metadata)` - store new window mapping
  - `lookup(case_number)` - retrieve window_id, auto-validates and removes if stale
  - `remove(case_number)` - explicitly remove entry
- **Class-based implementation**: Implement as WindowRegistry class with methods - object-oriented, holds database connection, testable with mocking

### Claude's Discretion
- Window existence validation architecture (platform-specific validators vs callback-based)
- How callers obtain WindowRegistry instance (explicit instantiation vs factory vs DI)
- Return values from register() operation (None vs bool vs dict)
- Exact retry timing parameters and max retry count
- Database file location (following existing config patterns)
- Error handling details and exception types

</decisions>

<specifics>
## Specific Ideas

- Registry integrates with existing terminal automation in Phase 12 codebase
- Must work across both macOS (iTerm2, Terminal.app) and Linux (gnome-terminal, konsole)
- Phase 16 will implement macOS window tracking that depends on this registry
- Integration test `test_duplicate_terminal_prevention_regression` is the primary validation signal

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 15-window-registry-foundation*
*Context gathered: 2026-02-07*

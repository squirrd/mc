# Phase 8: Type Safety & Modernization - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Add comprehensive type hints to all functions and upgrade minimum Python version to 3.11+ to make the codebase future-proof with modern Python standards. Include mypy type checking in CI pipeline and adopt modern Python syntax where appropriate.

</domain>

<decisions>
## Implementation Decisions

### Type hint coverage scope
- **All functions** get type hints, including private helpers and internal utilities
- **Third-party libraries**: Claude's discretion — use type: ignore, stubs, or workarounds based on criticality
- **Return types**: Claude's discretion — balance precision and readability, use detailed types where they add value
- **Complex structures**: Claude's discretion — TypedDict for frequently-used structures, dict[str, Any] for one-off API responses

### Type strictness level
- **Strictness**: Claude's discretion — choose appropriate mypy flags based on codebase complexity
- **Exceptions**: Claude's discretion — allow documented Any types or type: ignore with clear justification when practical
- **CI enforcement**: Claude's discretion — determine if hard requirement or warning based on current coverage
- **Goal**: Balance bug prevention and documentation — use strict typing where it catches real issues

### Python version target
- **Minimum version**: Python 3.11 (or latest stable if 9+ months old, otherwise latest-1 minor version)
- **Modern syntax**: Use new features (match/case, | unions, improved error messages) to make code more pythonic
- **Version pinning**: Development uses latest Python, but UAT/PROD environments lock Python version and dependencies to prevent surprise breakage
- **Type syntax**: Claude's discretion — consistently use modern syntax (X | Y, list[str]) throughout

### Migration strategy
- **Approach**: Claude's discretion — all at once vs module-by-module based on codebase size
- **Validation**: Claude's discretion — ensure tests pass and mypy validates appropriately
- **Runtime checking**: Claude's discretion — add beartype/pydantic only at critical boundaries (external inputs, config)
- **Bug discovery**: Claude's discretion — fix obvious safety issues revealed by typing, defer complex bugs to follow-up

### Claude's Discretion
- Specific mypy configuration flags to enable
- Whether to create .pyi stub files for third-party libraries
- Level of detail in return type annotations
- Use of TypedDict vs generic dict for API responses
- Migration approach (all at once vs incremental)
- Runtime type checking library choice and scope
- How to handle typing-revealed bugs (fix vs document)
- CI enforcement level (hard fail vs warning)

</decisions>

<specifics>
## Specific Ideas

**Python version strategy:**
- Development: Use latest stable Python for best developer experience
- Production: Lock Python version + all dependencies to prevent breaking changes from updates
- Version selection: Python 3.11 minimum, but prefer latest if stable for 9+ months, otherwise latest-1 minor version

**Type checking goals:**
- Balance bug prevention and documentation value
- Use strict typing where it catches real issues
- Don't over-engineer types where they don't add value

**Modern syntax adoption:**
- Embrace match/case, | unions, and other Python 3.11+ features
- Make code more pythonic and readable
- Modernize beyond just adding type hints

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-type-safety-&-modernization*
*Context gathered: 2026-01-22*

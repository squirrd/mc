# External Integrations

**Analysis Date:** 2026-01-20

## APIs & External Services

**Red Hat Support API:**
- Purpose: Fetch case details, account information, attachments, and comments
- SDK/Client: Custom client in `src/mc/integrations/redhat_api.py`
- Base URL: `https://api.access.redhat.com/support/v1`
- Auth: Bearer token via environment variable `RH_API_OFFLINE_TOKEN`
- Endpoints used:
  - `GET /cases/{case_number}` - Fetch case details
  - `GET /accounts/{account_number}` - Fetch account details
  - `GET /cases/{case_number}/attachments/` - List case attachments
  - File downloads via attachment URLs with streaming

**Red Hat SSO (Authentication):**
- Purpose: Convert offline token to access token
- Endpoint: `https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token`
- Auth: OAuth2 refresh token flow
- Client ID: `rhsm-api`
- Implementation: `src/mc/utils/auth.py` - `get_access_token()` function

**Red Hat LDAP:**
- Purpose: Employee directory search
- Server: `ldaps://ldap.corp.redhat.com`
- Base DN: `dc=redhat,dc=com`
- Protocol: LDAP via `ldapsearch` command-line tool (not Python SDK)
- Search: Queries by uid or cn fields
- Result limit: 10 entries (`-z 10`)
- Implementation: `src/mc/integrations/ldap.py`

**Salesforce (Red Hat GSS):**
- Purpose: Case viewing in web browser
- URL pattern: `https://gss--c.vf.force.com/apex/Case_View?sbstr={case_number}`
- Integration: URL generation and browser launching only (no API calls)
- Implementation: `src/mc/cli/commands/other.py` - `go()` function

## Data Storage

**Databases:**
- None - No database integration

**File Storage:**
- Local filesystem only
- Base directory: Configurable via `MC_BASE_DIR` environment variable
- Structure: `{base_dir}/{case_number}/` for workspace organization
- Attachments downloaded to: `{workspace}/attachments/`
- No cloud storage integration

**Caching:**
- None - No caching layer implemented

## Authentication & Identity

**Auth Provider:**
- Red Hat SSO (Keycloak-based)
- Implementation: OAuth2 offline token workflow
  - Offline token stored in `RH_API_OFFLINE_TOKEN` environment variable
  - Token refresh on each command execution via `get_access_token()`
  - Access token used as Bearer token for API requests
  - No token caching between invocations

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- stdout/stderr only via Python `print()` statements
- No structured logging framework
- No log aggregation

## CI/CD & Deployment

**Hosting:**
- Local CLI installation via pip
- No hosted service

**CI Pipeline:**
- None - No CI/CD configuration files present
- Manual testing via shell scripts in `tests/` directory

**Container Registry:**
- Base image: Red Hat UBI9 from `registry.access.redhat.com/ubi9/ubi:latest`
- No custom image publishing configured

## Environment Configuration

**Required env vars:**
- `RH_API_OFFLINE_TOKEN` - Red Hat API offline token (obtain from https://access.redhat.com/management/api)

**Optional env vars:**
- `MC_BASE_DIR` - Base directory for case workspaces (default varies, hardcoded in `src/mc/cli/main.py`)
- `MC_IMAGE_TAG` - Container image tag override (documented in `.env.example`)

**Secrets location:**
- Environment variables only
- `.env` file supported (not tracked in git)
- `.env.example` provided as template

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## System Dependencies

**macOS:**
- Chrome browser at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- Used by: `mc go --launch` command

**LDAP Tools:**
- `ldapsearch` command-line utility
- Required by: `mc ls` command
- Typically available via OpenLDAP package

**Container Tools:**
- Podman - Planned for container orchestration (not yet implemented)
- Container CLI tools in containerfile: `oc`, `kubectl`, `ocm`, `ocm-backplane`

---

*Integration audit: 2026-01-20*

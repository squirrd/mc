"""Agent-mode backplane login: reads cluster_id and runs ocm backplane login."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from mc.container.state import StateDatabase


_TOKEN_EXPIRY_SIGNALS = [
    "token is expired",
    "token expired",
    "unauthorized",
    "please login",
    "re-authenticate",
    "401",
]


def validate_cluster_id(cluster_id: str) -> bool:
    """Return True if cluster_id passes basic format check.

    Accepts alphanumeric strings with hyphens, total length 8-64 characters.
    First and last characters must be alphanumeric.
    """
    cluster_id = cluster_id.strip()
    if not cluster_id:
        return False
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]{6,62}[a-zA-Z0-9]$", cluster_id))


def _is_token_expired(stderr_output: str) -> bool:
    """Check if OCM error output indicates token expiry."""
    lower = stderr_output.lower()
    return any(phrase in lower for phrase in _TOKEN_EXPIRY_SIGNALS)


def _read_sfdc_cluster_id(case_dir: str) -> str:
    """Read cluster_id from sfdc-case.json. Returns '' if file absent or field missing."""
    sfdc_path = os.path.join(case_dir, "sfdc-case.json")
    try:
        with open(sfdc_path) as f:
            data = json.load(f)
        return str(data.get("openshiftClusterID") or "").strip()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""


def _get_state_db(state_db: StateDatabase | None) -> StateDatabase | None:
    """Return state_db if provided, else attempt to construct default. Returns None on failure."""
    if state_db is not None:
        return state_db
    try:
        return StateDatabase()
    except Exception:
        return None


def run_backplane_login(
    case_number: str,
    case_dir: str = "/case",
    state_db: StateDatabase | None = None,
) -> None:
    """Run ocm backplane login for the given case.

    Priority:
    1. sfdc-case.json openshiftClusterID (authoritative, not persisted)
    2. StateDatabase stored cluster_id (from prior successful user-entered login)
    3. User prompt (persisted to StateDatabase on success)

    Login failure is non-fatal — shell opens regardless.
    """
    db = _get_state_db(state_db)

    # Step 1: Try sfdc-case.json (highest priority)
    cluster_id = _read_sfdc_cluster_id(case_dir)
    cluster_id_source = "sfdc"

    # Step 2: Fall back to StateDatabase
    if not cluster_id and db is not None:
        try:
            meta = db.get_container(case_number)
            if meta and meta.cluster_id:
                cluster_id = meta.cluster_id
                cluster_id_source = "state_db"
        except Exception:
            pass

    # Step 3: Prompt user
    if not cluster_id:
        cluster_id_source = "user"
        try:
            user_input = input("Enter cluster ID (or press Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not user_input:
            return
        if not validate_cluster_id(user_input):
            print("Warning: cluster ID format invalid — skipping backplane login")
            return
        cluster_id = user_input

    # Step 4: Run ocm backplane login
    try:
        result = subprocess.run(
            ["ocm", "backplane", "login", cluster_id],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("Warning: ocm binary not found — skipping backplane login")
        return
    except subprocess.TimeoutExpired:
        print("Warning: backplane login timed out — continuing without cluster login")
        return

    # Print output (printed before exec bash so user sees login result)
    if result.stdout:
        sys.stdout.write(result.stdout)
        sys.stdout.flush()
    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()

    # Step 5: Handle result
    if result.returncode != 0:
        if _is_token_expired(result.stderr):
            print("OCM token expired — run 'ocm login' to re-authenticate")
        else:
            print(
                f"Warning: backplane login failed (exit {result.returncode}) — continuing without cluster login"
            )

        # Clear stored cluster_id so next session prompts fresh
        if db is not None:
            try:
                db.update_container(case_number, cluster_id="")
            except Exception:
                pass
        return

    # Step 6: Persist user-entered cluster_id on success (sfdc and state_db sources are not re-persisted)
    if cluster_id_source == "user" and db is not None:
        try:
            db.update_container(case_number, cluster_id=cluster_id)
        except Exception:
            pass

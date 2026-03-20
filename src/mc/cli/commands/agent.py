"""Agent-mode CLI commands (run inside container)."""
from __future__ import annotations

import argparse
import logging
import os
import sys

logger = logging.getLogger(__name__)


def init_case(args: argparse.Namespace) -> None:
    """Run case data initialization inside container.

    Fetches case metadata from Red Hat API and writes structured files
    to the case workspace directory (/case/).

    Case number is read from the CASE_NUMBER environment variable, which
    is set by ContainerManager when launching the container.
    """
    from mc.agent.case_data import init_case_data

    case_number = os.environ.get("CASE_NUMBER", "").strip()
    if not case_number:
        print("Error: CASE_NUMBER environment variable not set", file=sys.stderr)
        sys.exit(1)

    init_case_data(case_number)


def backplane_login(args: argparse.Namespace) -> None:
    """Run ocm backplane login for the current case (agent-mode command).

    Reads cluster_id from /case/sfdc-case.json, falls back to StateDatabase,
    prompts user if needed, then runs ocm backplane login. Non-fatal on failure.
    """
    from mc.agent.backplane_login import run_backplane_login

    case_number = os.environ.get("CASE_NUMBER", "").strip()
    if not case_number:
        logger.warning("CASE_NUMBER environment variable not set — skipping backplane login")
        return

    run_backplane_login(case_number)

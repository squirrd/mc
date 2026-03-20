"""Agent-mode CLI commands (run inside container)."""
from __future__ import annotations

import argparse
import os
import sys


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

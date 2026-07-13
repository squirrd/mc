"""Unit tests for mc jira CLI command."""

from __future__ import annotations

import argparse

from mc.cli.commands.jira import jira_command


class TestJiraCommandExists:
    """Basic existence and callable checks for jira_command."""

    def test_jira_command_is_callable(self) -> None:
        assert callable(jira_command)

    def test_jira_command_accepts_args_parameter(self) -> None:
        """jira_command must accept an argparse.Namespace argument."""
        import inspect
        sig = inspect.signature(jira_command)
        params = list(sig.parameters.keys())
        assert len(params) >= 1, "jira_command must accept at least one parameter"

#!/usr/bin/env python3
"""
Automated Integration Test Fixer

This script orchestrates parallel bug fixing for failed integration tests:
1. Runs all integration tests
2. Identifies failures
3. Creates parallel fix branches
4. Can be used manually or as basis for Claude Code skill

Usage:
    python scripts/fix_integration_tests.py [--parallel] [--dry-run]

This is designed to work with Claude Code agents to parallelize the work.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class TestFailure:
    """Represents a failed test case."""
    test_file: str
    test_name: str
    error_message: str
    error_type: str
    full_traceback: str

    @property
    def test_id(self) -> str:
        """Unique identifier for this test."""
        return f"{self.test_file}::{self.test_name}"

    @property
    def branch_name(self) -> str:
        """Suggested git branch name for fixing this test."""
        # Extract meaningful name from test function
        name = self.test_name.replace("test_", "").replace("_", "-")
        return f"fix/{name}"


class IntegrationTestRunner:
    """Runs integration tests and collects failures."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_dir = project_root / "tests" / "integration"

    def run_all_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Run all integration tests and collect results.

        Returns:
            Dict with 'passed', 'failed', 'skipped' counts and failure details
        """
        print("🧪 Running all integration tests...")
        print(f"   Test directory: {self.test_dir}")
        print()

        cmd = [
            "uv", "run", "pytest",
            str(self.test_dir),
            "-v",
            "--no-cov",
            "--tb=short",
            "--json-report",
            "--json-report-file=test_results.json"
        ]

        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True
        )

        # Parse pytest output
        failures = self._parse_pytest_output(result.stdout, result.stderr)

        return {
            "exit_code": result.exit_code,
            "passed": result.exit_code == 0,
            "failures": failures,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> List[TestFailure]:
        """Parse pytest output to extract failure information."""
        failures = []

        # Simple parsing - look for FAILED lines
        for line in stdout.split('\n'):
            if line.strip().startswith('FAILED'):
                # Example: FAILED tests/integration/test_case_terminal.py::test_fresh_install - Failed: ...
                parts = line.split(' ', 2)
                if len(parts) >= 2:
                    test_id = parts[1]
                    if '::' in test_id:
                        file_path, test_name = test_id.rsplit('::', 1)

                        # Extract error message (simplified)
                        error_msg = parts[2] if len(parts) > 2 else "Unknown error"

                        failures.append(TestFailure(
                            test_file=file_path,
                            test_name=test_name,
                            error_message=error_msg,
                            error_type="RuntimeError",  # Simplified
                            full_traceback=stderr
                        ))

        return failures


class FixOrchestrator:
    """Orchestrates parallel bug fixing workflow."""

    def __init__(self, project_root: Path, dry_run: bool = False):
        self.project_root = project_root
        self.dry_run = dry_run
        self.current_branch = self._get_current_branch()

    def _get_current_branch(self) -> str:
        """Get current git branch."""
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def create_fix_plan(self, failures: List[TestFailure]) -> Dict[str, Any]:
        """
        Create a structured plan for fixing failures.

        Returns:
            Plan dict with tasks for parallel execution
        """
        plan = {
            "total_failures": len(failures),
            "current_branch": self.current_branch,
            "tasks": []
        }

        for idx, failure in enumerate(failures, 1):
            task = {
                "id": idx,
                "test_id": failure.test_id,
                "test_file": failure.test_file,
                "test_name": failure.test_name,
                "branch_name": failure.branch_name,
                "error_message": failure.error_message,
                "actions": [
                    f"Create branch: {failure.branch_name}",
                    f"Analyze failure in {failure.test_file}",
                    "Identify root cause",
                    "Fix bug in source code",
                    f"Run test: {failure.test_id}",
                    "Commit fix if test passes"
                ],
                "agent_prompt": self._generate_agent_prompt(failure)
            }
            plan["tasks"].append(task)

        return plan

    def _generate_agent_prompt(self, failure: TestFailure) -> str:
        """Generate prompt for Claude Code agent to fix this specific failure."""
        return f"""Fix integration test failure: {failure.test_name}

**Test:** {failure.test_id}
**Error:** {failure.error_message}

**Workflow:**
1. Create branch: {failure.branch_name}
2. Run the specific test to understand the failure:
   ```
   uv run pytest {failure.test_id} -v -s
   ```
3. Read the test code to understand expectations
4. Identify the bug in the source code
5. Fix the bug
6. Re-run the test to verify fix
7. Commit the fix with message:
   ```
   fix: {failure.test_name.replace('test_', '').replace('_', ' ')}

   Fixes integration test: {failure.test_name}
   ```

**Current branch to return to:** {self.current_branch}

Please fix this bug and report back with:
- What was the root cause?
- What files did you change?
- Does the test pass now?
"""

    def print_plan(self, plan: Dict[str, Any]) -> None:
        """Pretty print the fix plan."""
        print()
        print("=" * 80)
        print("🔧 FIX PLAN - INTEGRATION TEST FAILURES")
        print("=" * 80)
        print()
        print(f"Total failures: {plan['total_failures']}")
        print(f"Current branch: {plan['current_branch']}")
        print()

        for task in plan['tasks']:
            print(f"Task {task['id']}: {task['test_name']}")
            print(f"  Branch: {task['branch_name']}")
            print(f"  Test:   {task['test_id']}")
            print(f"  Error:  {task['error_message'][:100]}...")
            print()

        print("=" * 80)
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automated integration test fixer")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel fixing")
    parser.add_argument("--dry-run", action="store_true", help="Don't make any changes")
    parser.add_argument("--export-plan", type=str, help="Export fix plan to JSON file")

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    # Phase 1: Run tests and collect failures
    runner = IntegrationTestRunner(project_root)
    results = runner.run_all_tests()

    failures = results["failures"]

    if not failures:
        print("✅ All integration tests passed!")
        return 0

    print(f"❌ Found {len(failures)} failed test(s)")
    print()

    # Phase 2: Create fix plan
    orchestrator = FixOrchestrator(project_root, dry_run=args.dry_run)
    plan = orchestrator.create_fix_plan(failures)
    orchestrator.print_plan(plan)

    # Export plan if requested
    if args.export_plan:
        plan_path = Path(args.export_plan)
        with open(plan_path, 'w') as f:
            json.dump(plan, f, indent=2)
        print(f"📝 Fix plan exported to: {plan_path}")
        print()

    # Print instructions for parallel execution
    if args.parallel:
        print("🚀 PARALLEL EXECUTION MODE")
        print()
        print("To fix these in parallel using Claude Code agents:")
        print()
        for task in plan['tasks']:
            print(f"# Agent {task['id']}:")
            print(f"# {task['agent_prompt'].split(chr(10))[0]}")
            print()
    else:
        print("💡 TIP: Run with --parallel to see parallel execution instructions")
        print("💡 TIP: Use --export-plan plan.json to export for Claude Code agents")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

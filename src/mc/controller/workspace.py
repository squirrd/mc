"""Workspace management for cases."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mc.exceptions import WorkspaceError
from mc.utils.formatters import shorten_and_format
from mc.utils.file_ops import create_file, create_directory

if TYPE_CHECKING:
    from mc.controller.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages case workspace files and directories."""

    def __init__(self, base_dir: str | Path, case_number: str, account_name: str, case_summary: str) -> None:
        """
        Initialize workspace manager.

        Args:
            base_dir: Base directory for all cases
            case_number: Case number
            account_name: Account name (will be formatted)
            case_summary: Case summary (will be formatted)
        """
        self.base_dir = Path(base_dir)

        # Validate base_dir exists and is a directory
        if not self.base_dir.exists():
            raise WorkspaceError(
                f"Base directory does not exist: {self.base_dir}",
                f"Try: Create it with 'mkdir -p {self.base_dir}'"
            )
        if not self.base_dir.is_dir():
            raise WorkspaceError(
                f"Base path is not a directory: {self.base_dir}",
                "Check: Path conflicts with existing file"
            )

        self.case_number = case_number
        self.account_name_formatted = shorten_and_format(account_name)
        self.case_summary_formatted = shorten_and_format(case_summary)
        self.file_dir_list = self._generate_file_dir_list()

    def _generate_file_dir_list(self) -> list[tuple[str, Path]]:
        """
        Generate list of expected files and directories for workspace.

        Returns:
            list: List of tuples (type, path) where type is 'D' or 'F'
        """
        try:
            file_dir_list = []
            case_dir = (
                self.base_dir /
                self.account_name_formatted /
                f"{self.case_number}-{self.case_summary_formatted}"
            )

            # Add directories (leaf directories only)
            file_dir_list.append(("D", case_dir / "files"))
            file_dir_list.append(("D", case_dir / "files" / "attach"))
            file_dir_list.append(("D", case_dir / "files" / "dp"))
            file_dir_list.append(("D", case_dir / "files" / "cp"))

            # Add files
            file_dir_list.append(("F", case_dir / "00-caseComments.md"))
            file_dir_list.append(("F", case_dir / "10-notes.md"))
            file_dir_list.append(("F", case_dir / "20-notes.md"))
            file_dir_list.append(("F", case_dir / "30-notes.md"))
            file_dir_list.append(("F", case_dir / "80-scratch.md"))

            return file_dir_list
        except OSError as e:
            raise WorkspaceError(
                f"Failed to construct workspace path: {e}",
                "Check: Account name and case summary contain valid characters"
            )

    def check(self) -> str:
        """
        Check workspace file status.

        Returns:
            str: Status - 'OK', 'WARN', or 'FATAL'
        """
        logger.info("Checking file status for case: %s", self.case_number)
        file_check = []

        for file_type, file_path in self.file_dir_list:
            logger.debug("  Type: %s, Path: %s", file_type, file_path)
            if file_path.exists():
                if file_path.is_file() and file_type == "F":
                    file_check.append("OK")
                    logger.debug("    OK")
                elif file_path.is_dir() and file_type == "D":
                    file_check.append("OK")
                    logger.debug("    OK")
                else:
                    file_check.append("WrongType")
                    actual_type = 'file' if file_path.is_file() else 'directory'
                    expected_type = 'file' if file_type == "F" else 'directory'
                    logger.error("    FATAL - Expected %s, found %s", expected_type, actual_type)
            else:
                file_check.append("Missing")
                logger.warning("    WARN - does not exist")

        # Determine overall status
        status = "OK"
        for fc in file_check:
            if fc == "Missing":
                status = "WARN"
            elif fc == "WrongType":
                status = "FATAL"
                break

        logger.info("CheckStatus: %s", status)
        return status

    def create_files(self) -> None:
        """Create all workspace files and directories."""
        for file_type, file_path in self.file_dir_list:
            logger.debug("  Type: %s, Path: %s", file_type, file_path)
            if file_type == "F":
                create_file(file_path)
            else:
                create_directory(file_path)

    def get_attachment_dir(self) -> Path | None:
        """Get the attachment directory path.

        Returns:
            Path: Attachment directory path or None if not found
        """
        for file_type, file_path in self.file_dir_list:
            if file_path.name == 'attach':
                return file_path
        return None

    @classmethod
    def from_case_number(
        cls,
        case_number: str,
        cache_manager: "CacheManager",
        base_dir: Path
    ) -> "WorkspaceManager":
        """Create WorkspaceManager from case number using Salesforce metadata.

        Convenience method for creating WorkspaceManager when you have a case
        number but need to fetch customer name and case summary from Salesforce.

        Args:
            case_number: Case number to resolve
            cache_manager: CacheManager for fetching case metadata
            base_dir: Base directory for workspaces

        Returns:
            WorkspaceManager instance with Salesforce-sourced metadata

        Raises:
            WorkspaceError: If case metadata missing required fields
        """
        from mc.controller.case_resolver import CaseResolver

        resolver = CaseResolver(cache_manager, base_dir)
        return resolver.get_workspace_manager(case_number)

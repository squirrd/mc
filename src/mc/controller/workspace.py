"""Workspace management for cases."""

import os
from mc.utils.formatters import shorten_and_format
from mc.utils.file_ops import create_file, create_directory


class WorkspaceManager:
    """Manages case workspace files and directories."""

    def __init__(self, base_dir, case_number, account_name, case_summary):
        """
        Initialize workspace manager.

        Args:
            base_dir: Base directory for all cases
            case_number: Case number
            account_name: Account name (will be formatted)
            case_summary: Case summary (will be formatted)
        """
        self.base_dir = base_dir
        self.case_number = case_number
        self.account_name_formatted = shorten_and_format(account_name)
        self.case_summary_formatted = shorten_and_format(case_summary)
        self.file_dir_list = self._generate_file_dir_list()

    def _generate_file_dir_list(self):
        """
        Generate list of expected files and directories for workspace.

        Returns:
            list: List of tuples (type, path) where type is 'D' or 'F'
        """
        file_dir_list = []
        case_dir = f"{self.base_dir}/{self.account_name_formatted}/{self.case_number}-{self.case_summary_formatted}"

        # Add directories (leaf directories only)
        file_dir_list.append(("D", f"{case_dir}/files"))
        file_dir_list.append(("D", f"{case_dir}/files/attach"))
        file_dir_list.append(("D", f"{case_dir}/files/dp"))
        file_dir_list.append(("D", f"{case_dir}/files/cp"))

        # Add files
        file_dir_list.append(("F", f"{case_dir}/00-caseComments.md"))
        file_dir_list.append(("F", f"{case_dir}/10-notes.md"))
        file_dir_list.append(("F", f"{case_dir}/20-notes.md"))
        file_dir_list.append(("F", f"{case_dir}/30-notes.md"))
        file_dir_list.append(("F", f"{case_dir}/80-scratch.md"))

        return file_dir_list

    def check(self):
        """
        Check workspace file status.

        Returns:
            str: Status - 'OK', 'WARN', or 'FATAL'
        """
        print(f"Checking file status for case: {self.case_number}")
        file_check = []

        for file_type, file_path in self.file_dir_list:
            print(f"  Type: {file_type}, Path: {file_path}")
            if os.path.exists(file_path):
                if os.path.isfile(file_path) and file_type == "F":
                    file_check.append("OK")
                    print("    OK")
                elif os.path.isdir(file_path) and file_type == "D":
                    file_check.append("OK")
                    print("    OK")
                else:
                    file_check.append("WrongType")
                    print("    FATAL - Wrong file type")
            else:
                file_check.append("Missing")
                print(f"    WARN - does not exist")

        # Determine overall status
        status = "OK"
        for fc in file_check:
            if fc == "Missing":
                status = "WARN"
            elif fc == "WrongType":
                status = "FATAL"
                break

        print(f"CheckStatus: {status}")
        return status

    def create_files(self):
        """Create all workspace files and directories."""
        for file_type, file_path in self.file_dir_list:
            print(f"  Type: {file_type}, Path: {file_path}")
            if file_type == "F":
                create_file(file_path)
            else:
                create_directory(file_path)

    def get_attachment_dir(self):
        """Get the attachment directory path."""
        for file_type, file_path in self.file_dir_list:
            if file_path.endswith('/attach'):
                return file_path
        return None

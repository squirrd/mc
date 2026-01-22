#!/usr/bin/env python3
"""Main entry point for mc CLI."""

import argparse
import os
import sys
from mc.cli.commands import case, other
from mc.config.manager import ConfigManager
from mc.config.wizard import run_setup_wizard
from mc.utils.file_ops import does_path_exist
from mc.version import get_version


def check_legacy_env_vars():
    """Check for deprecated environment variables and guide migration."""
    legacy_vars = ["MC_BASE_DIR", "RH_API_OFFLINE_TOKEN"]
    found_vars = [var for var in legacy_vars if var in os.environ]

    if not found_vars:
        return

    # Detect shell for tailored instructions
    shell = os.environ.get("SHELL", "").lower()

    if "fish" in shell:
        unset_cmd = "\n".join(f"set -e {var}" for var in found_vars)
    else:  # bash/zsh
        unset_cmd = "\n".join(f"unset {var}" for var in found_vars)

    print(f"ERROR: Legacy environment variables detected: {', '.join(found_vars)}")
    print("\nEnvironment variables are no longer supported.")
    print("Configuration is now managed via config file.")
    print("\nTo migrate:")
    print("1. Remove environment variables:")
    print(f"\n{unset_cmd}\n")
    print("2. Run 'mc --help' to trigger configuration wizard")
    sys.exit(1)


def main():
    """Main CLI entry point."""
    # Create argument parser early to handle --version/--help without config
    parser = argparse.ArgumentParser(prog='mc', description='MC CLI tool')
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {get_version()}')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Attach subcommand
    parser_attach = subparsers.add_parser('attach', help='Download attachments for a case')
    parser_attach.add_argument('case_number', type=str, help='Case number')

    # Check subcommand
    parser_check = subparsers.add_parser('check', help='Check the state of a workspace for a case')
    parser_check.add_argument('case_number', type=str, help='Case number')
    parser_check.add_argument('-f', '--fix', action='store_true')

    # Create subcommand
    parser_create = subparsers.add_parser('create', help='Create a workspace for a case')
    parser_create.add_argument('case_number', type=str, help='Case number')
    parser_create.add_argument('-d', '--download', action='store_true')

    # Case Comments subcommand (renamed from login)
    parser_comments = subparsers.add_parser('case-comments', help='Display case comments')
    parser_comments.add_argument('case_number', type=str, help='Case number')

    # LDAP Search subcommand
    parser_ls = subparsers.add_parser('ls', help='Search for a user in LDAP')
    parser_ls.add_argument('uid', type=str, help='The UID to search for in LDAP')
    parser_ls.add_argument('-A', '--all', action='store_true')

    # Go subcommand
    parser_go = subparsers.add_parser('go', help='Print or launch Salesforce case URL')
    parser_go.add_argument('case_number', type=str, help='Case number')
    parser_go.add_argument('-l', '--launch', action='store_true', help='Launch URL in Chrome')

    # Parse arguments (--version/--help exit here, before config check)
    args = parser.parse_args()

    # Check for legacy environment variables
    check_legacy_env_vars()

    # Load or create configuration
    config_mgr = ConfigManager()
    if not config_mgr.exists():
        print("No config file found. Running setup wizard...")
        print()
        config = run_setup_wizard()
        config_mgr.save(config)
    else:
        config = config_mgr.load()

    # Get configuration values
    base_dir = config["base_directory"]
    offline_token = config["api"]["offline_token"]

    # Verify base directory exists
    if not does_path_exist(base_dir):
        print(f"The directory '{base_dir}' must exist")
        exit(1)

    # Route to appropriate command
    if args.command == 'attach':
        case.attach(args.case_number, base_dir, offline_token)
    elif args.command == 'check':
        case.check(args.case_number, base_dir, offline_token, fix=args.fix)
    elif args.command == 'create':
        case.create(args.case_number, base_dir, offline_token, download=args.download)
    elif args.command == 'case-comments':
        case.case_comments(args.case_number, offline_token)
    elif args.command == 'ls':
        other.ls(args.uid, show_all=args.all)
    elif args.command == 'go':
        other.go(args.case_number, launch=args.launch)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

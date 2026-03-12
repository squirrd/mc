#!/usr/bin/env python3
"""Main entry point for mc CLI."""

import argparse
import logging
import os
import sys
from typing import Literal, cast
from mc.cli.commands import case, container, other
from mc.config.manager import ConfigManager
from mc.config.wizard import run_setup_wizard
from mc.exceptions import MCError
from mc.runtime import get_runtime_mode
from mc.utils.errors import handle_cli_error
from mc.utils.file_ops import does_path_exist
from mc.utils.logging import setup_logging
from mc.banner import show_update_banner
from mc.version import get_version

ExitCode = Literal[0, 1, 2, 65, 69, 73, 74, 130]


def main() -> ExitCode:
    """Main CLI entry point."""
    try:
        # Check for quick access pattern (mc <case_number>) before parsing
        if len(sys.argv) > 1 and sys.argv[1].isdigit() and len(sys.argv[1]) == 8:
            # Quick access: mc <case_number>
            # Insert 'quick_access' as the command
            sys.argv = [sys.argv[0], 'quick_access'] + sys.argv[1:]

        # Create argument parser early to handle --version/--help without config
        parser = argparse.ArgumentParser(prog='mc', description='MC CLI tool')
        parser.add_argument('--version', action='version',
                            version=f'%(prog)s {get_version()}')
        parser.add_argument('--debug', action='store_true',
                            help='Enable debug logging')
        parser.add_argument('--json-logs', action='store_true',
                            help='Output logs as JSON (for CI/automation)')
        parser.add_argument('--debug-file', type=str,
                            help='Write debug logs to file')
        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Attach subcommand
        parser_attach = subparsers.add_parser('attach', help='Download attachments for a case')
        parser_attach.add_argument('case_number', type=str, help='Case number')
        parser_attach.add_argument('--serial', action='store_true',
                                    help='Download attachments one at a time (for debugging)')
        parser_attach.add_argument('--quiet', action='store_true',
                                    help='Suppress progress output (errors only)')

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

        # Case Terminal subcommand (Phase 12 - terminal attachment)
        parser_case = subparsers.add_parser('case', help='Attach terminal to case container')
        parser_case.add_argument('case_number', type=str, help='Case number')

        # LDAP Search subcommand
        parser_ls = subparsers.add_parser('ls', help='Search for a user in LDAP')
        parser_ls.add_argument('uid', type=str, help='The UID to search for in LDAP')
        parser_ls.add_argument('-A', '--all', action='store_true')

        # Go subcommand
        parser_go = subparsers.add_parser('go', help='Print or launch Salesforce case URL')
        parser_go.add_argument('case_number', type=str, help='Case number')
        parser_go.add_argument('-l', '--link', action='store_true', help='Print URL instead of launching browser')

        # Container subcommand
        container_parser = subparsers.add_parser('container', help='Container lifecycle operations')
        container_subparsers = container_parser.add_subparsers(dest='container_command')

        container_subparsers.add_parser('list', help='List all containers')

        create_parser = container_subparsers.add_parser('create', help='Create container')
        create_parser.add_argument('case_number', help='Case number')

        stop_parser = container_subparsers.add_parser('stop', help='Stop container')
        stop_parser.add_argument('case_numbers', nargs='+', help='Case number(s)')

        delete_parser = container_subparsers.add_parser('delete', help='Delete container')
        delete_parser.add_argument('case_numbers', nargs='+', help='Case number(s)')

        exec_parser = container_subparsers.add_parser('exec', help='Execute command in container')
        exec_parser.add_argument('case_number', help='Case number')
        exec_parser.add_argument('command', nargs='+', help='Command to execute')

        # Reconcile window registry
        reconcile_parser = container_subparsers.add_parser(
            'reconcile',
            help='Reconcile window registry with actual terminal windows'
        )

        # Quick access subcommand (hidden, used via mc <case_number>)
        quick_parser = subparsers.add_parser('quick_access', help=argparse.SUPPRESS)
        quick_parser.add_argument('case_number', type=str, help='Case number')

        # Version subcommand
        version_parser = subparsers.add_parser('version', help='Show version and check for updates')
        version_parser.add_argument('--update', action='store_true',
                                    help='Force immediate version check (bypasses hourly throttle)')

        # Parse arguments (--version/--help exit here, before config check)
        args = parser.parse_args()

        # Configure logging early (before any operations that might log)
        logger = setup_logging(
            json_logs=args.json_logs,
            debug=args.debug,
            debug_file=getattr(args, 'debug_file', None)
        )

        # Load or create configuration
        config_mgr = ConfigManager()
        if not config_mgr.exists():
            # Use print for setup wizard trigger since it's before main execution
            print("No config file found. Running setup wizard...")  # print OK
            print()  # print OK
            config = run_setup_wizard()
            config_mgr.save(config)
        else:
            config = config_mgr.load()

        # Get configuration values with defaults for backwards compatibility
        base_dir = config.get("base_directory", os.path.expanduser("~/mc"))

        # Try new key first, fall back to old key for backwards compatibility
        offline_token = config.get("api", {}).get("rh_api_offline_token") or config.get("api", {}).get("offline_token")

        # Warn if using deprecated key
        if not config.get("api", {}).get("rh_api_offline_token") and config.get("api", {}).get("offline_token"):
            logger.warning("Config key 'api.offline_token' is deprecated. Please rename to 'api.rh_api_offline_token' in your config file.")

        # Verify base directory exists
        if not does_path_exist(base_dir):
            logger.error("The directory '%s' must exist", base_dir)
            return 1

        # Show update banner (foreground check, once per calendar day, suppressed for --version)
        if get_runtime_mode() != 'agent':
            try:
                show_update_banner()
            except Exception as e:
                logger.debug("Update banner failed: %s", e)

        # Route to appropriate command
        if args.command == 'attach':
            case.attach(args.case_number, base_dir, offline_token,
                       serial=args.serial, quiet=args.quiet)
        elif args.command == 'check':
            case.check(args.case_number, base_dir, offline_token, fix=args.fix)
        elif args.command == 'create':
            case.create(args.case_number, base_dir, offline_token, download=args.download)
        elif args.command == 'case-comments':
            case.case_comments(args.case_number, offline_token)
        elif args.command == 'case':
            # Import here to avoid circular dependency
            from mc.cli.commands.container import case_terminal
            case_terminal(args)
        elif args.command == 'ls':
            other.ls(args.uid, show_all=args.all)
        elif args.command == 'go':
            other.go(args.case_number, launch=not args.link)
        elif args.command == 'container':
            if args.container_command == 'list':
                container.list_containers(args)
            elif args.container_command == 'create':
                container.create(args)
            elif args.container_command == 'stop':
                container.stop(args)
            elif args.container_command == 'delete':
                container.delete(args)
            elif args.container_command == 'exec':
                container.exec_command(args)
            elif args.container_command == 'reconcile':
                container.reconcile_windows(args)
            else:
                container_parser.print_help()
        elif args.command == 'quick_access':
            container.quick_access(args)
        elif args.command == 'version':
            other.version(update=args.update)
        else:
            parser.print_help()

        return 0  # Success

    except MCError as e:
        # Handle MC-specific errors with proper exit codes
        debug_mode = '--debug' in sys.argv
        return cast(ExitCode, handle_cli_error(e, debug=debug_mode))

    except KeyboardInterrupt:
        # Handle user interruption (Ctrl+C)
        # Use print since this is a terminal event
        print("\nInterrupted by user", file=sys.stderr)  # print OK
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        # Handle unexpected errors
        logger = logging.getLogger(__name__)
        logger.exception("Unexpected error occurred")

        # In debug mode, show full traceback
        debug_mode = '--debug' in sys.argv
        if debug_mode:
            raise

        # Otherwise use logger for error message
        logger.error("Unexpected error: %s", e)
        return 1


if __name__ == '__main__':
    sys.exit(main())

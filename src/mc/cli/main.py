#!/usr/bin/env python3
"""Main entry point for mc CLI."""

import argparse
import os
from mc.cli.commands import case, other
from mc.utils.file_ops import does_path_exist


def main():
    """Main CLI entry point."""
    # Set base directory
    base_dir = "/Users/dsquirre/Cases"

    # Verify base directory exists
    if not does_path_exist(base_dir):
        print(f"The directory '{base_dir}' must exist")
        exit(1)

    # Verify offline token is set
    offline_token = os.environ.get('RH_API_OFFLINE_TOKEN', None)
    if offline_token is None:
        print("The env variable 'RH_API_OFFLINE_TOKEN' must be set")
        exit(1)

    # Create argument parser
    parser = argparse.ArgumentParser(prog='mc', description='MC CLI tool')
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

    # Parse arguments
    args = parser.parse_args()

    # Route to appropriate command
    if args.command == 'attach':
        case.attach(args.case_number, base_dir)
    elif args.command == 'check':
        case.check(args.case_number, base_dir, fix=args.fix)
    elif args.command == 'create':
        case.create(args.case_number, base_dir, download=args.download)
    elif args.command == 'case-comments':
        case.case_comments(args.case_number)
    elif args.command == 'ls':
        other.ls(args.uid, show_all=args.all)
    elif args.command == 'go':
        other.go(args.case_number, launch=args.launch)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

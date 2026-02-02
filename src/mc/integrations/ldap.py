"""LDAP search integration."""

import logging
import re
import subprocess

logger = logging.getLogger(__name__)


def ldap_search(uid: str, show_all: bool = False) -> tuple[bool, str]:
    """
    Search LDAP for a user and display their details.

    Args:
        uid: User ID to search for
        show_all: If True, show raw LDAP output

    Returns:
        tuple: (success: bool, output: str)
    """
    # Validate search term length
    if not (4 <= len(uid) <= 15):
        return False, f"Search term '{uid}' must be between 4 and 15 characters"

    # Determine search pattern
    if not (5 <= len(uid) < 15):
        search_term = f"(uid=*{uid}*)"
    else:
        search_term = f"(|(uid=*{uid}*)(cn=*{uid}*))"

    logger.info("Searching LDAP for: %s", search_term)

    # Execute ldapsearch command
    # ldapsearch is a standard system utility, not user-controlled
    # nosec B602
    command = [
        "ldapsearch",  # nosec B607
        "-LLL",
        "-z", "10",
        "-x",
        "-H", "ldaps://ldap.corp.redhat.com",
        "-b", "dc=redhat,dc=com",
        search_term
    ]

    try:
        # LDAP search using subprocess is safe - command and args are hardcoded,
        # only search_term parameter is user input and it's validated (length 4-15)
        # nosec B603
        result = subprocess.run(command, capture_output=True, text=True, check=True)  # nosec B603
        output = result.stdout
    except FileNotFoundError:
        return False, "Error: 'ldapsearch' command not found. Is it installed and in your PATH?"
    except subprocess.CalledProcessError as e:
        return False, f"Error executing ldapsearch: {e.stderr}"

    if not output.strip():
        return False, "No results found."

    if show_all:
        # Intentional user output - raw LDAP data
        print(output)  # print OK
        return True, output

    # Format and print results
    print_ldap_cards(output)
    return True, output


def print_ldap_cards(output: str) -> None:
    """
    Print formatted LDAP user information cards with error handling.

    Args:
        output: Raw LDAP output string
    """
    # The order of keys in this list determines the display order.
    ordered_keys = [
        ('cn', 'Name'),
        ('rhatJobTitle', 'RH Title'),
        ('title', 'Title'),
        ('manager', 'Manager'),
        ('l', 'City'),
        ('st', 'State'),
        ('co', 'Country'),
        ('uid', 'UID'),
        ('rhatOriginalHireDate', 'Hire Date'),
        ('mobile', 'Mobile')
    ]
    field_map = dict(ordered_keys)

    entries_processed = 0
    entries_failed = 0

    for entry in output.strip().split('\n\n'):
        if not entry.strip():
            continue

        try:
            user_data = {}
            for line in entry.split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        if key in field_map:
                            user_data[key] = value.strip()

            # Only print if we got at least one field
            if not user_data:
                logger.warning("Skipping empty LDAP entry")
                entries_failed += 1
                continue

            # Intentional user output - formatted LDAP card
            print("-" * 40)  # print OK
            for key, display_name in ordered_keys:
                # Use .get() instead of direct access to handle missing fields
                if key in user_data:
                    value = user_data[key]
                    # Special formatting for the manager field
                    if key == 'manager':
                        try:
                            manager_uid = re.search(r'uid=([^,]+)', value)
                            display_value = manager_uid.group(1) if manager_uid else value
                        except (AttributeError, IndexError):
                            display_value = value
                    else:
                        display_value = value
                    print(f"{display_name:<12}: {display_value}")  # print OK
            print("-" * 40)  # print OK
            entries_processed += 1

        except Exception as e:
            # Log but continue processing other entries
            logger.warning("Failed to parse LDAP entry: %s", e)
            entries_failed += 1
            continue

    if entries_failed > 0:
        logger.info("Processed %d entries, %d failed to parse", entries_processed, entries_failed)

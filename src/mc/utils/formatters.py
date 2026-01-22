"""String formatting utilities."""

import re


def shorten_and_format(input_string: str) -> str:
    """
    Shorten and format a string for use in file/directory names.

    - Substrings all words to 7 characters
    - Removes non-alphanumeric characters
    - Replaces spaces and hyphens with underscores
    - Limits total length to 22 characters

    Args:
        input_string: The string to format

    Returns:
        Formatted string suitable for file/directory names
    """
    # Step 1: Substring all words and words both sides of "-" to 7 characters
    words = re.split(r'(\s+|-)', input_string)
    processed_words = [word[:7] if word.strip() and word != '-' else word for word in words]

    # Step 2: Join the words back together
    joined = ''.join(processed_words)

    # Step 3: Remove all non-alphanumeric characters and replace with "_"
    alphanumeric = re.sub(r'[^a-zA-Z0-9\s-]', '_', joined)

    # Step 4: Replace all spaces and "-" with "_", avoid duplicates
    result = re.sub(r'[\s-]+', '_', alphanumeric)

    # Step 5: Remove any duplicate underscores
    result = re.sub(r'_+', '_', result)

    # Step 6: Remove leading/trailing underscores
    result = result.strip('_')[:22]

    return result

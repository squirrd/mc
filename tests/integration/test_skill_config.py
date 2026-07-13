"""Integration tests for Claude Code skill configuration files.

Validates that skill YAML frontmatter is well-formed and contains
the expected content for correct skill matching by Claude Code.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


SKILL_DIR = Path.home() / ".claude" / "skills"
TDD_RELEASE_SKILL = SKILL_DIR / "tdd-release" / "skill.md"


def _parse_frontmatter(path: Path) -> dict:
    """Extract and parse YAML frontmatter from a skill.md file."""
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {path}")
    return yaml.safe_load(match.group(1))


@pytest.mark.integration
def test_mc_121_release_trigger_desc_update_description_acceptance():
    """Acceptance test for MC-121 update-description slice.

    Feature : MC-121-release-trigger-desc
    Slice   : update-description
    Criterion: The skill.md description field leads with trigger words
               (merge, release, ship, cut a release, combine branches) so
               Claude Code matches the skill when the user says any of these.

    The description must contain ALL of these trigger words/phrases
    in its text so the skill matching algorithm picks it up.
    """
    assert TDD_RELEASE_SKILL.exists(), f"Skill file not found: {TDD_RELEASE_SKILL}"

    frontmatter = _parse_frontmatter(TDD_RELEASE_SKILL)
    description = frontmatter.get("description", "")

    # The description must lead with / prominently contain trigger words
    required_triggers = ["merge", "ship", "cut a release", "combine branches"]
    missing = [t for t in required_triggers if t.lower() not in description.lower()]
    assert not missing, (
        f"Description is missing trigger words: {missing}\n"
        f"Current description: {description!r}"
    )


@pytest.mark.integration
def test_mc_121_release_trigger_desc_validate_frontmatter_acceptance():
    """Acceptance test for MC-121 validate-frontmatter slice.

    Feature : MC-121-release-trigger-desc
    Slice   : validate-frontmatter
    Criterion: The modified YAML frontmatter with multiline description
               parses correctly with no syntax errors, and the description
               is a multiline block (not a single line).

    A multiline YAML block scalar (|- or |) must be used so the description
    contains line breaks and can include both trigger words and functional text.
    """
    assert TDD_RELEASE_SKILL.exists(), f"Skill file not found: {TDD_RELEASE_SKILL}"

    frontmatter = _parse_frontmatter(TDD_RELEASE_SKILL)

    # All required keys must still be present after the edit
    required_keys = ["name", "description", "argument-hint", "allowed-tools"]
    missing_keys = [k for k in required_keys if k not in frontmatter]
    assert not missing_keys, f"Frontmatter missing required keys: {missing_keys}"

    description = frontmatter.get("description", "")

    # The description must be multiline (contains newline characters)
    # A single-line description means the |- block scalar was not used
    assert "\n" in description, (
        f"Description must be a multiline YAML block scalar (use |- or |), "
        f"but it is a single line: {description!r}"
    )


@pytest.mark.integration
def test_mc_121_release_trigger_desc_verify_listing_acceptance():
    """Acceptance test for MC-121 verify-listing slice.

    Feature : MC-121-release-trigger-desc
    Slice   : verify-listing
    Criterion: The skill description includes the exclusion statement
               about being the ONLY correct way to merge branches, so
               Claude Code knows to route merge requests to this skill.

    The exclusion statement must be present so Claude Code can distinguish
    between general git merge operations and the tdd-release workflow.
    """
    assert TDD_RELEASE_SKILL.exists(), f"Skill file not found: {TDD_RELEASE_SKILL}"

    frontmatter = _parse_frontmatter(TDD_RELEASE_SKILL)
    description = frontmatter.get("description", "")

    # Must contain the exclusion/routing statement
    assert "only correct way to merge branches" in description.lower(), (
        f"Description must include exclusion statement about being the "
        f"'ONLY correct way to merge branches', but it does not.\n"
        f"Current description: {description!r}"
    )

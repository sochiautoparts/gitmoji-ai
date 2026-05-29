"""
Team configuration — shared commit conventions via .gitmoji-ai-team.yml

This file can be committed to the repo so all team members follow the same rules.
"""

import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import yaml

logger = __import__("logging").getLogger(__name__)

TEAM_CONFIG_FILENAME = ".gitmoji-ai-team.yml"

DEFAULT_TEAM_CONFIG = """# GitMoji AI Team Configuration
# Commit this file to your repo to enforce team conventions.

# Required commit types (only these types are allowed)
# If empty, all conventional types are allowed.
required_types: []

# Required scopes (commits must include one of these scopes)
# If empty, no scope is required.
required_scopes: []

# Maximum subject line length (characters)
max_subject_length: 72

# Custom type aliases (map custom type to conventional type)
# Example: feature -> feat, bugfix -> fix
custom_types: {}

# Commit style for the team
# Options: conventional, emoji, plain, semantic-release, gitmoji-dict
commit_style: conventional

# Language for commit messages
# Options: en, ru, es, de, fr, ja, zh
language: en

# Require scope in commit messages
require_scope: false

# Disallow certain types
disallowed_types: []

# Footer requirements
require_footer: false
footer_template: ""

# Changelog format
# Options: keepachangelog, angular
changelog_format: keepachangelog
"""


@dataclass
class TeamConfig:
    """Parsed team configuration"""
    required_types: list[str] = field(default_factory=list)
    required_scopes: list[str] = field(default_factory=list)
    max_subject_length: int = 72
    custom_types: dict[str, str] = field(default_factory=dict)
    commit_style: str = "conventional"
    language: str = "en"
    require_scope: bool = False
    disallowed_types: list[str] = field(default_factory=list)
    require_footer: bool = False
    footer_template: str = ""
    changelog_format: str = "keepachangelog"


def find_team_config(repo_path: str = ".") -> Optional[Path]:
    """Find .gitmoji-ai-team.yml by walking up from repo_path to root."""
    current = Path(repo_path).resolve()
    while True:
        candidate = current / TEAM_CONFIG_FILENAME
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_team_config(repo_path: str = ".") -> Optional[TeamConfig]:
    """Load and parse the team config file. Returns None if not found."""
    config_path = find_team_config(repo_path)
    if not config_path:
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return TeamConfig(
            required_types=data.get("required_types", []),
            required_scopes=data.get("required_scopes", []),
            max_subject_length=data.get("max_subject_length", 72),
            custom_types=data.get("custom_types", {}),
            commit_style=data.get("commit_style", "conventional"),
            language=data.get("language", "en"),
            require_scope=data.get("require_scope", False),
            disallowed_types=data.get("disallowed_types", []),
            require_footer=data.get("require_footer", False),
            footer_template=data.get("footer_template", ""),
            changelog_format=data.get("changelog_format", "keepachangelog"),
        )
    except Exception as exc:
        logger.warning("Failed to load team config: %s", exc)
        return None


def init_team_config(repo_path: str = ".") -> Path:
    """Create a .gitmoji-ai-team.yml file in the repo root."""
    # Find git root
    git_dir = Path(repo_path) / ".git"
    if not git_dir.exists():
        # Walk up
        current = Path(repo_path).resolve()
        while not (current / ".git").exists():
            parent = current.parent
            if parent == current:
                raise FileNotFoundError("Not a git repository")
            current = parent
        repo_root = current
    else:
        repo_root = Path(repo_path).resolve()

    config_path = repo_root / TEAM_CONFIG_FILENAME
    if config_path.exists():
        raise FileExistsError(f"{TEAM_CONFIG_FILENAME} already exists at {config_path}")

    config_path.write_text(DEFAULT_TEAM_CONFIG, encoding="utf-8")
    return config_path


def validate_commit_against_team(
    message: str,
    config: TeamConfig,
) -> list[str]:
    """Validate a commit message against team rules. Returns list of violations."""
    violations = []

    # Parse the commit message
    # Pattern: type(scope): description
    pattern = r'^(\w+)(?:\(([^)]+)\))?:\s*(.+)$'
    match = re.match(pattern, message)

    if not match:
        # Not conventional commit format
        if config.required_types or config.require_scope:
            violations.append("Commit message must follow Conventional Commits format: type(scope): description")
        return violations

    msg_type = match.group(1)
    scope = match.group(2) or ""
    description = match.group(3)

    # Check required types
    if config.required_types and msg_type not in config.required_types:
        # Check custom type aliases
        resolved_type = config.custom_types.get(msg_type)
        if resolved_type not in config.required_types:
            violations.append(
                f"Type '{msg_type}' not allowed. Allowed types: {', '.join(config.required_types)}"
            )

    # Check disallowed types
    if msg_type in config.disallowed_types:
        violations.append(f"Type '{msg_type}' is disallowed by team rules")

    # Check required scope
    if config.require_scope and not scope:
        violations.append("Scope is required by team rules")

    # Check required scopes
    if config.required_scopes and scope and scope not in config.required_scopes:
        violations.append(
            f"Scope '{scope}' not allowed. Allowed scopes: {', '.join(config.required_scopes)}"
        )

    # Check subject length
    subject_len = len(description)
    if subject_len > config.max_subject_length:
        violations.append(
            f"Subject too long ({subject_len} chars). Max: {config.max_subject_length}"
        )

    return violations


def check_team_compliance(repo_path: str = ".") -> dict:
    """Check if recent commits comply with team rules. Returns summary dict."""
    config = load_team_config(repo_path)
    if not config:
        return {"has_team_config": False, "violations": [], "total_checked": 0}

    from gitmoji_ai.git_ops import get_recent_commits
    commits = get_recent_commits(20, repo_path)

    all_violations = []
    for commit in commits:
        subject = commit["subject"]
        violations = validate_commit_against_team(subject, config)
        for v in violations:
            all_violations.append({
                "commit": commit["hash"][:7],
                "subject": subject,
                "violation": v,
            })

    return {
        "has_team_config": True,
        "total_checked": len(commits),
        "violations": all_violations,
        "config": config,
    }

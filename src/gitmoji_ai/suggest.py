"""
Quick suggest command — for git hooks integration
Outputs a single commit message without interactive prompts
"""

import asyncio
import sys
from gitmoji_ai.git_ops import get_staged_diff, get_unstaged_diff
from gitmoji_ai.ai_engine import generate_commit_messages
from gitmoji_ai.config import get_settings
from gitmoji_ai.usage import check_limit, is_pro


def suggest_commit(path: str = ".", language: str = "en", style: str = "conventional") -> str:
    """Generate a single commit suggestion (non-interactive, for hooks)"""
    
    # Check rate limits — free users have limited commits per month
    allowed, remaining = check_limit("commit")
    if not allowed:
        print("⚠️ Monthly commit limit reached. Upgrade to Pro for unlimited.", file=sys.stderr)
        return ""

    diff = get_staged_diff(path)
    if not diff:
        diff = get_unstaged_diff(path)
    if not diff:
        return ""

    suggestions = asyncio.run(generate_commit_messages(diff, language, style))
    if suggestions:
        message = suggestions[0].message
        # Add watermark for free tier
        if not is_pro():
            message += " (gitmoji-ai free)"
        return message
    return ""

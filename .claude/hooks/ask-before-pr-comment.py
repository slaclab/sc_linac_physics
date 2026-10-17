#!/usr/bin/env python3
"""PreToolUse hook: ask a person before Claude posts to a PR or issue.

Auto-fix sessions are woken by review comments and can answer them on
GitHub unattended. This hook makes any Bash command that would post a
comment, a review, or a reply stop at a permission prompt instead, so the
author reads the reply first. Reading (gh pr view, gh api GET) is not
affected.

Matched:
- gh pr comment, gh pr review, gh issue comment
- gh pr/issue close or reopen with --comment/-c
- any gh api call that writes: -X/--method other than GET, a field flag
  (-f/-F/--field/--raw-field/--input, value attached or not), or a
  graphql mutation
- any command that talks to api.github.com directly (curl, wget, http)

The check is a pattern match on the command text, so it catches the ways
a session normally posts, not a deliberate attempt to hide one. If the
hook itself fails, it asks rather than letting the command through.
"""

import json
import re
import sys

POSTING_SUBCOMMANDS = re.compile(
    r"\bgh\s+(pr\s+(comment|review)|issue\s+comment)\b"
    # close and reopen post their --comment/-c text as a comment
    r"|\bgh\s+(pr|issue)\s+(close|reopen)\b.*\s(-c|--comment)\b"
)
GH_API = re.compile(r"\bgh\s+api\b")
WRITE_METHOD = re.compile(
    r"(-X|--method)[\s=]*['\"]?(?!GET\b)[A-Z]+", re.IGNORECASE
)
FIELD_FLAG = re.compile(r"(^|\s)(-[fF]|--field|--raw-field|--input)(\s|=|\S)")
GRAPHQL_MUTATION = re.compile(r"\bmutation\b", re.IGNORECASE)
DIRECT_API = re.compile(r"api\.github\.com", re.IGNORECASE)

ASK = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": (
            "This may post to GitHub. A person reviews replies to PR "
            "comments before they go out."
        ),
    }
}


def posts_to_github(command: str) -> bool:
    if POSTING_SUBCOMMANDS.search(command) or DIRECT_API.search(command):
        return True
    if not GH_API.search(command):
        return False
    return bool(
        WRITE_METHOD.search(command)
        or FIELD_FLAG.search(command)
        or GRAPHQL_MUTATION.search(command)
    )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        should_ask = posts_to_github(command)
    except Exception:
        should_ask = True
    if should_ask:
        json.dump(ASK, sys.stdout)


if __name__ == "__main__":
    main()

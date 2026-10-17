#!/usr/bin/env python3
"""PreToolUse hook: ask a person before Claude posts to a PR or issue.

Auto-fix sessions are woken by review comments and can answer them on
GitHub unattended. This hook makes any Bash command that would post a
comment, a review, or a reply stop at a permission prompt instead, so the
author reads the reply first. Reading (gh pr view, gh api GET) is not
affected.

Matched, wherever `gh` appears in the command (after ;, &&, |, $( ...):
- gh pr comment / review / close / reopen, gh issue comment / close /
  reopen (close and reopen can carry a --comment)
- any gh api call that writes: -X/--method other than GET, a field flag
  (-f/-F/--field/--raw-field/--input, value attached or not), or a
  graphql mutation
- any command that talks to api.github.com directly (curl, wget, http)

The command is split the way the shell splits it (backslash-newline
joined, quotes removed), and -R/--repo is skipped wherever it sits, so
`gh -R o/r pr comment` and `'-fbody=x'` are caught. It still catches the
ways a session normally posts, not a deliberate attempt to hide one. If
the command can't be parsed, or the hook itself fails, it asks.
"""

import json
import re
import shlex
import sys

POSTING = {
    "pr": {"comment", "review", "close", "reopen"},
    "issue": {"comment", "close", "reopen"},
}
REPO_FLAGS = {"-R", "--repo"}
FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field", "--input")
SHELL_OPERATORS = set(";&|()<>")
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


def split_commands(command: str) -> list[list[str]]:
    """Shell-split `command` into simple commands at ;, &&, |, ( and )."""
    lexer = shlex.shlex(
        command.replace("\\\n", ""), posix=True, punctuation_chars=True
    )
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token and set(token) <= SHELL_OPERATORS:
            commands.append(current)
            current = []
        else:
            current.append(token)
    commands.append(current)
    return [words for words in commands if words]


def gh_args(words: list[str]) -> list[str] | None:
    """The arguments after `gh` in one simple command, or None."""
    for i, word in enumerate(words):
        if word == "gh" or word.endswith("/gh"):
            return words[i + 1 :]
    return None


def positionals(args: list[str]) -> list[str]:
    """Non-flag arguments, skipping the value that follows -R/--repo."""
    found, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in REPO_FLAGS:
            skip = True
        elif not arg.startswith("-"):
            found.append(arg)
    return found


def api_writes(args: list[str]) -> bool:
    for i, arg in enumerate(args):
        if arg in ("-X", "--method"):
            method = args[i + 1] if i + 1 < len(args) else ""
        elif arg.startswith("--method="):
            method = arg.split("=", 1)[1]
        elif arg.startswith("-X"):
            method = arg[2:]
        else:
            method = None
        if method is not None and method.upper() != "GET":
            return True
        if arg.startswith(FIELD_FLAGS) or "mutation" in arg.lower():
            return True
    return False


def posts_to_github(command: str) -> bool:
    if DIRECT_API.search(command):
        return True
    for words in split_commands(command):
        args = gh_args(words)
        if args is None:
            continue
        pos = positionals(args)
        if len(pos) >= 2 and pos[1] in POSTING.get(pos[0], ()):
            return True
        if pos[:1] == ["api"] and api_writes(args):
            return True
    return False


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

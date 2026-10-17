#!/usr/bin/env python3
"""PreToolUse hook: ask a person before Claude posts to a PR or issue.

Auto-fix sessions are woken by review comments and can answer them on
GitHub unattended. This hook makes any Bash command that would post a
comment, a review, or a reply stop at a permission prompt instead, so the
author reads the reply first. Reading (gh pr view, gh api GET) is not
affected.

Matched, wherever `gh` appears in the command (after ;, &&, |, a newline,
$( or a backtick, or inside a quoted string such as bash -c "..."):
- gh pr comment / review / close / reopen, gh issue comment / close /
  reopen (close and reopen can carry a --comment)
- any gh api call that writes: -X/--method other than GET, a field flag
  (-f/-F/--field/--raw-field/--input, value attached or not, or f/F/X
  inside a combined short-flag group), or a graphql mutation
- any command that talks to api.github.com directly (curl, wget, http)

Not matched: replying to, or resolving the thread of, an inline review
comment whose author GitHub marks as a bot (Copilot, github-actions). The
hook looks the author up with a read-only gh api call. If the lookup
fails, it asks.

The command is split the way the shell splits it (backslash-newline
joined, quotes removed), and -R/--repo is skipped wherever it sits, so
`gh -R o/r pr comment` and `'-fbody=x'` are caught. It still catches the
ways a session normally posts, not a deliberate attempt to hide one. If
the command can't be parsed, or the hook itself fails, it asks.
"""

import json
import re
import shlex
import subprocess
import sys

POSTING = {
    "pr": {"comment", "review", "close", "reopen"},
    "issue": {"comment", "close", "reopen"},
}
REPO_FLAGS = {"-R", "--repo"}
LONG_WRITE_FLAGS = ("--field", "--raw-field", "--input")
SHELL_OPERATORS = set(";&|()<>")
DIRECT_API = re.compile(r"api\.github\.com", re.IGNORECASE)
# gh api repos/OWNER/REPO/pulls/N/comments/ID/replies (OWNER/REPO may be
# gh's {owner}/{repo} placeholders, which the lookup passes through)
REPLY_ENDPOINT = re.compile(
    r"/?repos/([^/\s]+/[^/\s]+)/pulls/\d+/comments/(\d+)/replies"
)
THREAD_ID = re.compile(r"threadId\s*:\s*\\?\"([A-Za-z0-9_-]+)\\?\"")
MAX_NESTING = 3

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
    """Shell-split `command` into simple commands.

    Splits at ;, &, |, (, ), <, >, newlines and backticks. A newline or
    backtick inside quotes becomes a ";" inside that quoted word, which
    only changes text the hook never acts on.
    """
    text = command.replace("\\\n", "").replace("\n", ";").replace("`", ";")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands, current = [], []
    for token in lexer:
        if token and set(token) <= SHELL_OPERATORS:
            commands.append(current)
            current = []
        else:
            current.append(token)
    commands.append(current)
    return [words for words in commands if words]


def gh_calls(words: list[str]) -> list[list[str]]:
    """The arguments after each `gh` in one simple command."""
    return [
        words[i + 1 :]
        for i, word in enumerate(words)
        if word == "gh" or word.endswith("/gh")
    ]


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


def method_arg(args: list[str], i: int) -> str | None:
    """The HTTP method args[i] sets with -X/--method, or None."""
    arg = args[i]
    if arg in ("-X", "--method"):
        return args[i + 1] if i + 1 < len(args) else ""
    if arg.startswith("--method="):
        return arg.split("=", 1)[1]
    if arg.startswith("-X"):
        return arg[2:]
    return None


def api_writes(args: list[str]) -> bool:
    for i, arg in enumerate(args):
        method = method_arg(args, i)
        if method is not None:
            if method.upper() != "GET":
                return True
        elif "mutation" in arg.lower() or arg.startswith(LONG_WRITE_FLAGS):
            return True
        elif arg.startswith("-") and not arg.startswith("--"):
            # A short-flag group such as -f, -fbody=x or -iXPOST: any f, F
            # or X among its leading letters can mean a write.
            letters = re.match(r"-([A-Za-z]*)", arg).group(1)
            if set(letters) & set("fFX"):
                return True
    return False


def gh_output(*args: str) -> str:
    """Run a read-only gh command; any failure raises, so the hook asks."""
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=10, check=True
    )
    return result.stdout.strip()


def reply_to_bot(pos: list[str]) -> bool:
    """True for a reply to an inline review comment written by a bot."""
    for arg in pos:
        match = REPLY_ENDPOINT.fullmatch(arg)
        if match:
            repo, comment_id = match.groups()
            user_type = gh_output(
                "api",
                f"repos/{repo}/pulls/comments/{comment_id}",
                "--jq",
                ".user.type",
            )
            return user_type == "Bot"
    return False


def resolves_bot_thread(args: list[str]) -> bool:
    """True for a graphql call whose only mutation resolves a bot's thread."""
    query = " ".join(args)
    if re.findall(r"(\w+)\s*\(\s*input\s*:", query) != ["resolveReviewThread"]:
        return False
    match = THREAD_ID.search(query)
    if not match:
        return False
    author = gh_output(
        "api",
        "graphql",
        "-f",
        'query=query { node(id: "%s") { ... on PullRequestReviewThread {'
        " comments(first: 1) { nodes { author { __typename } } } } } }"
        % match.group(1),
        "--jq",
        ".data.node.comments.nodes[0].author.__typename",
    )
    return author == "Bot"


def posts_to_github(command: str, depth: int = 0) -> bool:
    if DIRECT_API.search(command):
        return True
    if depth > MAX_NESTING:
        return True
    for words in split_commands(command):
        # A quoted word that is itself a command (bash -c "...", eval "...")
        if any(
            " " in word and "gh" in word and posts_to_github(word, depth + 1)
            for word in words
        ):
            return True
        for args in gh_calls(words):
            pos = positionals(args)
            if len(pos) >= 2 and pos[1] in POSTING.get(pos[0], ()):
                return True
            if pos[:1] == ["api"] and api_writes(args):
                if reply_to_bot(pos) or resolves_bot_thread(args):
                    continue
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

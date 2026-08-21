"""Collect operator-visible changes from the PRs in a release.

Reads the `## Operator-visible` section from each PR merged since the previous
tag and renders a short note for #srf-software. Changes that alter what an
operator sees or how an application behaves by default are easy to lose inside
a large PR; this surfaces them at release time without anyone remembering to.

Usage (in CI):
    python .github/scripts/operator_notes.py --tag v9.34.0

Emits the note on stdout and sets `has_notes` in $GITHUB_OUTPUT. Exits 0 with
no output when nothing operator-visible shipped, which is the common case.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Matches "## Operator-visible" through to the next H2 or end of body.
SECTION = re.compile(
    r"^##\s*Operator[- ]visible\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

# HTML comments (template guidance) should not reach Slack.
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

NOTHING = {"", "none", "none.", "n/a", "na", "-", "nothing"}

# Heredoc delimiter for the multi-line $GITHUB_OUTPUT value.
DELIMITER = "NOTE_EOF"


def fence_safe(text):
    """Stop note text from closing the $GITHUB_OUTPUT heredoc early.

    The note is built from PR descriptions, and a PR author can edit the
    description after the PR is merged. GitHub ends a multi-line output at
    the first line matching the delimiter exactly, so a body containing a
    bare `NOTE_EOF` line could append arbitrary `key=value` step outputs to
    this job. Indenting such a line keeps it in the value and inert.
    """
    return "\n".join(
        f" {line}" if line.strip() == DELIMITER else line
        for line in text.splitlines()
    )


def run(cmd):
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False
    ).stdout.strip()


def previous_tag(tag):
    """The tag immediately before `tag`, or empty for the first release."""
    prev = run(["git", "describe", "--tags", "--abbrev=0", f"{tag}^"])
    return prev


def merged_prs(since_tag, tag):
    """PR numbers referenced by commits in the range, oldest first."""
    rng = f"{since_tag}..{tag}" if since_tag else tag
    log = run(["git", "log", rng, "--pretty=format:%s%n%b"])
    seen, out = set(), []
    for n in re.findall(r"#(\d+)", log):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def operator_section(pr_number):
    """The cleaned Operator-visible text for a PR, or None."""
    raw = run(["gh", "pr", "view", pr_number, "--json", "body,title"])
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    body = data.get("body") or ""
    match = SECTION.search(body)
    if not match:
        return None

    text = COMMENT.sub("", match.group(1))
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = text.strip()

    if text.lower().strip(".") in {s.strip(".") for s in NOTHING}:
        return None
    if not text:
        return None

    return {"number": pr_number, "title": data.get("title", ""), "text": text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="the tag just released")
    ap.add_argument("--since", default=None, help="override previous tag")
    args = ap.parse_args()

    since = args.since if args.since is not None else previous_tag(args.tag)
    prs = merged_prs(since, args.tag)

    notes = [n for n in (operator_section(p) for p in prs) if n]

    out_path = os.environ.get("GITHUB_OUTPUT")

    if not notes:
        if out_path:
            with open(out_path, "a") as fh:
                fh.write("has_notes=false\n")
        return 0

    lines = [
        f"*{args.tag} is out* — operator-visible changes:",
        "",
    ]
    for n in notes:
        first, *rest = n["text"].splitlines()
        lines.append(f"• {first.strip()}  (#{n['number']})")
        for extra in rest:
            if extra.strip():
                lines.append(f"    {extra.strip()}")
    lines += [
        "",
        f"Full notes: https://github.com/slaclab/sc_linac_physics/releases/tag/{args.tag}",
    ]

    note = "\n".join(lines)
    print(note)

    if out_path:
        with open(out_path, "a") as fh:
            fh.write("has_notes=true\n")
            fh.write(f"note<<{DELIMITER}\n")
            fh.write(fence_safe(note) + "\n")
            fh.write(f"{DELIMITER}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

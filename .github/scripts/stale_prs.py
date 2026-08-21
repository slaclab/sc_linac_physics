"""List open PRs that have been waiting on review, for a weekly nudge.

A PR counts as waiting when it is not a draft, has no approving review, and
was opened at least `--days` ago. Drafts and changes-requested PRs are
excluded on the grounds that neither is blocked on a reviewer.

Usage (in CI):
    python .github/scripts/stale_prs.py --days 5

Emits the note on stdout and sets `has_stale` in $GITHUB_OUTPUT. Exits 0 with
no note when nothing is waiting, which is the goal state.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

# Heredoc delimiter for the multi-line $GITHUB_OUTPUT value.
DELIMITER = "STALE_EOF"

# reviewDecision values that mean nobody is waiting on a reviewer.
#
# Verified against slaclab/sc_linac_physics: because `main` is protected with
# required_approving_review_count = 1, GitHub always computes a decision, so
# unreviewed PRs come back as "REVIEW_REQUIRED" rather than "". A PR opened
# against an unprotected base branch does return "", and the field can be
# absent entirely. Testing for the excluded values rather than the included
# ones keeps all three cases ("REVIEW_REQUIRED", "", missing) reported.
NOT_WAITING = {"APPROVED", "CHANGES_REQUESTED"}

# Fields to request. Keep this list minimal: `gh` builds its GraphQL query
# from exactly these, so an unused field is an extra permission surface.
FIELDS = (
    "number,title,author,createdAt,isDraft,reviewDecision,reviewRequests,url"
)


def fence_safe(text):
    """Stop note text from closing the $GITHUB_OUTPUT heredoc early.

    GitHub ends a multi-line output at the first line matching the delimiter
    exactly, so a bare `STALE_EOF` line could append arbitrary `key=value`
    step outputs to this job. Indenting such a line keeps it inert.

    Nothing interpolated below can currently produce one -- PR titles, author
    logins and team names are all single-line -- so this is defensive only.
    It stops being defensive the moment anyone renders a PR body here.
    """
    return "\n".join(
        f" {line}" if line.strip() == DELIMITER else line
        for line in text.splitlines()
    )


def slack_escape(text):
    """Escape the three characters Slack treats as markup in `text` fields.

    Ampersand first, or the escapes introduced below get double-escaped.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fetch_prs(repo, limit):
    """Open PRs from the GitHub API, newest first.

    Surfaces gh's own stderr on failure. The likely first-run failure is the
    token lacking a scope for reviewDecision or reviewRequests, and "Resource
    not accessible by integration" says that; a bare traceback does not.
    """
    cmd = ["gh", "pr", "list", "--repo", repo, "--state", "open"]
    cmd += ["--limit", str(limit), "--json", FIELDS]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(
            f"gh pr list failed (exit {proc.returncode}); see stderr above"
        )
    return json.loads(proc.stdout)


def reviewer_name(request):
    """Display name for one reviewRequests entry.

    Users carry `login`. Teams carry `name` (display) and `slug`
    (org-qualified, e.g. "slaclab/srf") but no `login`, so prefer the
    shorter `name` and fall back to `slug`.
    """
    return request.get("login") or request.get("name") or request.get("slug")


def waiting_on_review(pr, now, stale_days):
    """A row dict if this PR is waiting on a reviewer, else None."""
    if pr.get("isDraft"):
        return None
    if pr.get("reviewDecision") in NOT_WAITING:
        return None

    opened = dt.datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
    age = (now - opened).days
    if age < stale_days:
        return None

    reviewers = [
        name
        for name in (reviewer_name(r) for r in pr.get("reviewRequests") or [])
        if name
    ]
    return {
        "number": pr["number"],
        "title": pr["title"],
        "author": (pr.get("author") or {}).get("login", "?"),
        "age": age,
        "reviewers": reviewers,
        "url": pr["url"],
    }


def render(rows, truncated):
    """Slack mrkdwn for the collected rows."""
    plural = "s" if len(rows) > 1 else ""
    lines = [f"*{len(rows)} PR{plural} waiting on review*", ""]

    for row in rows:
        who = ", ".join(f"@{slack_escape(r)}" for r in row["reviewers"])
        who = who or "_no reviewer requested_"
        lines.append(
            f"• <{row['url']}|#{row['number']}> "
            f"{slack_escape(row['title'])} — "
            f"{row['age']}d, by {slack_escape(row['author'])}, "
            f"waiting on {who}"
        )

    lines += [
        "",
        "_Open PRs with no approving review. Drafts and "
        "changes-requested excluded._",
    ]
    if truncated:
        # gh returns newest-first and truncates silently at --limit, so the
        # PRs dropped here are the oldest ones -- exactly the ones this job
        # exists to surface. Say so rather than under-reporting quietly.
        lines.append("_Hit the query limit; the oldest PRs may be missing._")
    return "\n".join(lines)


def write_output(note):
    """Set `has_stale` and `note` in $GITHUB_OUTPUT, when running in CI."""
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return

    with open(out_path, "a") as fh:
        if note is None:
            fh.write("has_stale=false\n")
            return
        fh.write("has_stale=true\n")
        fh.write(f"note<<{DELIMITER}\n")
        fh.write(fence_safe(note) + "\n")
        fh.write(f"{DELIMITER}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--days",
        type=int,
        default=5,
        help="days without an approving review before a PR is listed",
    )
    ap.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="owner/name (defaults to $GITHUB_REPOSITORY)",
    )
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    if not args.repo:
        ap.error("--repo is required when $GITHUB_REPOSITORY is unset")

    prs = fetch_prs(args.repo, args.limit)
    now = dt.datetime.now(dt.timezone.utc)

    rows = [
        row
        for row in (waiting_on_review(p, now, args.days) for p in prs)
        if row
    ]
    rows.sort(key=lambda r: -r["age"])

    if not rows:
        print(f"No PRs waiting on review beyond {args.days} days.")
        write_output(None)
        return 0

    note = render(rows, truncated=len(prs) >= args.limit)
    print(note)
    write_output(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())

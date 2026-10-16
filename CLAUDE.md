# CLAUDE.md

## Commands

```bash
# Run all tests (coverage is on by default; CI enforces 80%)
pytest

# Run a single test file
pytest tests/test_cli.py -v

# Lint
flake8 . --count --max-complexity=10 --max-line-length=120 --show-source --statistics
black --check .

# Format
black .

# Install for development
pip install -e ".[dev,test]"
```

Set `PYDM_DEFAULT_PROTOCOL=fake` to run UI code without live EPICS hardware.
Run these in the env you installed into. `No module named pytest` means the
wrong env, not a missing dependency.

## Documentation

Full documentation lives in [`docs/`](docs/index.md).

**Explainer vs. docs page.** An app's "how it works and why" lives in one
place: an explainer in `docs/explainers/`, for the app or for a piece several
apps share (`auto_tune.md`). That covers data flow, decisions, caveats and
`CHECK:` questions, each claim cited. The markdown page is a short
reference: the command, paths, how to add data, a file list, and a link to the
explainer. Don't tell the story in both. Why: two copies drift, and only cited
text is checked by `tests/docs/test_citations.py`. #323's explainer took 8
commits to keep current. Apps without an explainer keep their full page.

An explainer is a markdown page. Each interactive part is a small `.html`
widget in `docs/explainers/widgets/`, linked on a line of its own, which the
site shows inline. Why: prose diffs a reviewer can read, and the site's search
and sidebar.

## Architecture and testing

@AGENTS.md

## Scope and shipping

### Split at planning time, not review time

Before starting a piece of work, state how it will be split into PRs. If a task
can't be a sequence of independently mergeable changes, say so and why before
starting.

### Target PR size

Aim for **under 400 changed lines** excluding tests and generated files. Past
~800, split it. Large mechanical changes (renames, formatting, generated code)
are exempt but should be their own PR, never mixed with logic changes.

When a change is growing past the target mid-work, stop and propose a split
rather than continuing.

### Stacked PRs stay drafts

A PR whose branch builds on other unmerged PRs opens as a draft
(`gh pr create --draft`). It stays a draft until every PR it builds on has
merged. Start its description with "Stacked on #N" and say which commits to
review. Until then the diff includes the earlier PRs' commits. A draft also
keeps CODEOWNERS from requesting review before the PR can be read on its own.

### Flag operator-visible changes

If a change alters what a user sees or how an application behaves by default —
new or reordered UI, changed defaults, renamed commands, altered PV usage,
different launch behavior — say so explicitly in the PR description under the
`## Operator-visible` heading, in one or two sentences of plain language.

These need a short note to `#srf-software` when released. Fill in the PR
template (`.github/pull_request_template.md`) sections rather than deleting them.

### Record decisions with reasoning

When choosing between real alternatives — reusing production code vs.
reimplementing, staging a rollout, deferring a migration — write down the
reasoning, not just the outcome. A comment at the decision point is enough for
small calls; anything architectural goes in `docs/`.

### Write for every audience reading it

Several kinds of reader see this work, and each reads for something different:

- **Software experts** read the design: framework structure, phase
  sequencing, threading, persistence.
- **Machine experts** read machine behavior. They need to know exactly what
  the code commands the hardware to do, and how it derives the numbers people
  act on.
- **Operators** read what changes in what they see and run. They get the
  `## Operator-visible` note and the `#srf-software` release note, not the
  diff.

The list is not exhaustive. `.github/CODEOWNERS` maps each area to its
reviewers. Write so that any of these readers can follow without the author
there to explain.

#### Say what the code does. Do not explain what the hardware does.

This is the rule that matters most. Every written review comment on #284 and
#288 corrected a hardware explanation, not the code. Examples: the LCLS-II-HE
loaded-Q window follows from a different default Qext, not a "looser standard".
There is no active microphonics compensation, only slow drift feedback (cutoff a
few Hz). Cold landing is recorded before the stepper moves. Fluent wrong physics
costs the reviewer a fact-check instead of a read.

Two categories, treated differently:

**Derivable from this repo — assert it.** Which PV is written, in what units,
in what order, what value, what the code branches on, where a constant lives.
Checkable against the source by whoever is reading. This is most of what a
machine expert actually needs.

**A fact about the physical machine — cite it or flag it.** Why the hardware
behaves that way, feedback bandwidths, what happens inside the cavity, the
ordering of physical events the code does not itself control. If a source exists
in-repo, point at it. If not, write the claim as a question instead of a
sentence:

```python
# CHECK: is DF_COLD recorded before the stepper moves, or after?
```

Reviewers grep `CHECK:` and clear them in one pass. Three flagged questions beat
three confident sentences that turn out wrong.

#### The rest

- **Make PV writes obvious.** Any code path that puts a value to the machine
  should be readable without tracing three layers of indirection. Name the PV,
  the units, and the value.
- **State hardware assumptions as assumptions.** The code encodes expectations
  about tuner behavior, limit switches, piezo state, and cavity frequency
  response. Name the expectation and where it is relied on. Do not justify it.
- **Cite the arithmetic in analysis code.** In `q0/`, `quench_processing/`,
  `microphonics/`: name the relationship and where the constants came from, with
  a source. A silent change to a fit is a silent change to a physics conclusion.
  Cite rather than re-derive.
- **Flag anything that changes what the machine does**, even when the code
  change looks cosmetic. Reordered writes, changed defaults, adjusted timeouts.

`applications/rf_commissioning/` remains single-maintainer. Non-trivial changes
there should be readable by someone who did not write them — favor explicit
naming and docstrings on phase logic over compact code.

### How to write it

This governs PR descriptions, docs, comments, and chat replies. The audience
is any of the readers above, plus managers, all reading between other things.
Aim at what you would type in Slack, not at a technical report.

The failure mode runs backwards: the smallest PRs get the longest descriptions
(#292: 66 lines of CI config, 580 words).

**Budgets.** *What this changes*: 60 words. Each recorded decision: 80. If a
section needs more, the PR is probably too big — check the size comment.

**Register.** Lead with the verdict: "CI PR, no code touched." "Simple PR, just
colors and buttons." Say what the reader should do. Short sentences — if one
needs a comma to survive, split it. Hedge honestly ("my best guess is") rather
than elaborately.

**Cut on sight.** Restating what the diff already shows. Explaining at length
why a rejected alternative was rejected. Implementation detail nobody will act
on. Empty template headings — delete the heading rather than writing "None
tagged."

**Vocabulary: if it names something in the code, use it.** Cavity, detune,
cryomodule, piezo, SSA, chirp, `NSTEPS_COLD` — identifiers, PV names and
constants the reader can grep. No gloss needed. Jargon is the opposite: words
that exist only in prose. Orthogonal, idempotent, invariant, semantics,
pre-flight — none of them name anything in `src/`.
The test is grep over identifiers, not taste.

**People.** Refer to people by name or handle. Don't infer pronouns from a
name, username, or role; use they/them unless you know.

## Conventions

- Black 80-character line length; Flake8 allows up to 120 (the two tools have different limits — this is intentional).
- Releases use conventional commits (`feat`, `fix`, `perf`, `refactor`) and are published to GitHub Releases (not PyPI) via `python-semantic-release`.
- Packaged data (`.ui` files, `faults.csv`, Q0 calibration/example data) must be listed in `pyproject.toml` under `[tool.setuptools.package-data]` — CI verifies the built wheel contains them.

"""Check that `file.py:NNN` citations in prose still point where they claim.

Docs and comments in this repo cite the source by file and line — `stepper.py:96`,
`linac_utils.py:224-236`. CLAUDE.md asks for those citations because a claim a
reader can check against the source is worth more than one they have to take on
faith. But a line number is a claim about the code that rots the moment the code
moves, and nothing notices: the prose still reads fine, the citation still looks
authoritative, and it now points at something else.

Three failure modes, all of them silent:

1. The cited file is renamed or deleted.
2. The file shrinks past the cited line.
3. The line still exists but no longer holds what was cited. Only checkable when
   the citation names a symbol as well as a location, which is the convention
   worth keeping for exactly this reason:

       <span class="cite">INTEG_SP, piezo.py:41</span>

   That form is verifiable. A bare `piezo.py:41` is not.

A fourth is not rot but ambiguity: this repo has 12 colliding basenames, so
`frequency_tuning.py:66` could mean either of two files. The check asks for a
path-qualified citation rather than picking one.

The scans below pass trivially while no citations exist in a scanned file. The
tests at the bottom run each check against fixtures so the logic is proven
independently of whether the tree currently has anything to catch.

Not checked: continuation citations like `over_temp_ack_c, :807`, which take
their file from the preceding citation in the same span. Cite the file
explicitly and this will check it.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Where prose lives. Data directories are excluded by extension rather than by
# path: a .json fixture full of timestamps produces `1666731038.928921` matches
# that look nothing like a citation but cost time to rule out.
SCAN_GLOBS = ("src/**/*.py", "docs/**/*.md", "docs/**/*.html")

# Where cited files may live.
SOURCE_GLOBS = ("src/**/*.py",)

# `foo.py:12`, `a/b/foo.py:12`, `foo.py:12-34`. The path may be partial.
CITATION = re.compile(
    r"\b((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_]+\.py):(\d+)(?:-(\d+))?\b"
)

# `SYMBOL, foo.py:12` — a symbol named alongside its location. Allows
# `A/B` alternatives (`MODECTRL/MODESTAT`), a trailing `()`, and dotted
# attributes (`Cavity._auto_tune`).
SYMBOL_CITATION = re.compile(
    r"([A-Za-z_][A-Za-z0-9_.]*(?:/[A-Za-z_][A-Za-z0-9_.]*)*(?:\(\))?)"
    r"\s*,\s*"
    r"((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_]+\.py):(\d+)(?:-(\d+))?"
)

# How far from the cited line the named symbol may sit. A citation points at a
# block, not always its first line, and the block's name is usually at the top.
SYMBOL_WINDOW = 6


def _label(path):
    """Repo-relative path where possible, absolute otherwise.

    The fixture tests below build trees under tmp_path, which is outside the
    repo, so this cannot assume every path is relative to REPO_ROOT.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _scan_targets():
    return sorted(
        p for glob in SCAN_GLOBS for p in REPO_ROOT.glob(glob) if p.is_file()
    )


def _source_files():
    return sorted(
        p for glob in SOURCE_GLOBS for p in REPO_ROOT.glob(glob) if p.is_file()
    )


def resolve(cited_path, sources):
    """Every source file whose path ends with `cited_path`.

    Suffix matching so a citation can be as specific as it needs to be:
    `frequency_tuning.py` matches both copies, `phases/frequency_tuning.py`
    matches one.
    """
    wanted = tuple(cited_path.split("/"))
    return [p for p in sources if tuple(p.parts[-len(wanted) :]) == wanted]


def symbol_near(path, start, end, symbol):
    """Whether `symbol` appears within SYMBOL_WINDOW lines of the citation.

    `A/B` counts as found if either side is present — the form is used for PV
    pairs, where citing both lines but naming both symbols reads better than
    two separate citations.
    """
    lines = path.read_text(errors="replace").split("\n")
    lo = max(1, start - SYMBOL_WINDOW)
    hi = min(len(lines), (end or start) + SYMBOL_WINDOW)
    window = "\n".join(lines[lo - 1 : hi])
    names = [
        part.replace("()", "").split(".")[-1]
        for part in symbol.split("/")
        if part
    ]
    return any(name and name in window for name in names)


def collect(targets=None, sources=None):
    """Every citation found, as (origin, cited_path, start, end, symbol)."""
    targets = _scan_targets() if targets is None else targets
    sources = _source_files() if sources is None else sources
    found = []
    for target in targets:
        text = target.read_text(errors="replace")
        symbols = {
            (m.group(2), m.group(3), m.group(4)): m.group(1)
            for m in SYMBOL_CITATION.finditer(text)
        }
        for m in CITATION.finditer(text):
            key = (m.group(1), m.group(2), m.group(3))
            found.append(
                {
                    "origin": _label(target),
                    "path": m.group(1),
                    "start": int(m.group(2)),
                    "end": int(m.group(3)) if m.group(3) else None,
                    "symbol": symbols.get(key),
                }
            )
    return found, sources


def _describe(c):
    span = f"{c['start']}-{c['end']}" if c["end"] else str(c["start"])
    return f"{c['origin']} cites {c['path']}:{span}"


def unambiguous(citations, sources):
    """Pair each citation that resolves to exactly one file with that file.

    The bounds and symbol checks run only against these. A citation matching
    several files belongs to the ambiguity check, and running the other checks
    on it reports one root cause once per candidate, naming files the writer
    never meant.
    """
    pairs = []
    for c in citations:
        matches = resolve(c["path"], sources)
        if len(matches) == 1:
            pairs.append((c, matches[0]))
    return pairs


def test_cited_files_exist():
    """A citation naming a file that is not in the tree is stale on its face."""
    citations, sources = collect()
    missing = [c for c in citations if not resolve(c["path"], sources)]
    assert not missing, "citations naming no existing file:\n" + "\n".join(
        f"  {_describe(c)}" for c in missing
    )


def test_cited_lines_are_in_bounds():
    """The cited line must exist in the file it names.

    Ambiguous citations are skipped so one missing path prefix does not also
    surface here as an out-of-bounds error against a file nobody meant.
    """
    citations, sources = collect()
    bad = []
    for c, path in unambiguous(citations, sources):
        length = len(path.read_text(errors="replace").split("\n"))
        hi = c["end"] or c["start"]
        if hi > length:
            bad.append(
                f"  {_describe(c)} but {_label(path)} has {length} lines"
            )
    assert not bad, "citations past the end of the cited file:\n" + "\n".join(
        bad
    )


def test_ambiguous_citations_are_path_qualified():
    """A bare basename matching two source files does not identify one.

    Enough path is required to pick one even when a single candidate is long
    enough to hold the cited line. Resolving `frequency_tuning.py:743` by
    noticing the other copy stops at 448 lines is not what a reader does, and
    it breaks silently as soon as the short copy grows past the cited line.
    """
    citations, sources = collect()
    ambiguous = []
    for c in citations:
        matches = resolve(c["path"], sources)
        if len(matches) > 1:
            options = ", ".join(_label(p) for p in matches)
            ambiguous.append(f"  {_describe(c)} — could be any of: {options}")
    assert not ambiguous, (
        "citations that do not identify one file; add enough path to "
        "disambiguate:\n" + "\n".join(ambiguous)
    )


def test_named_symbols_appear_near_their_citation():
    """`SYMBOL, file.py:NNN` must have SYMBOL near line NNN.

    This is the check that catches drift rather than deletion: the file still
    exists, the line still exists, and it moved.
    """
    citations, sources = collect()
    drifted = []
    for c, path in unambiguous(citations, sources):
        if not c["symbol"]:
            continue
        length = len(path.read_text(errors="replace").split("\n"))
        if (c["end"] or c["start"]) > length:
            continue  # reported by the bounds test
        if not symbol_near(path, c["start"], c["end"], c["symbol"]):
            drifted.append(
                f"  {_describe(c)} — {c['symbol']!r} is not within "
                f"{SYMBOL_WINDOW} lines of there"
            )
    assert (
        not drifted
    ), "cited symbols not found near the line cited:\n" + "\n".join(drifted)


# ---------------------------------------------------------------------------
# The checks, against fixtures
#
# The scans above pass while nothing in the tree is cited, so they cannot show
# that the logic works. These can.
# ---------------------------------------------------------------------------


@pytest.fixture
def tree(tmp_path):
    """A miniature source tree with a basename collision in it."""
    a = tmp_path / "src" / "pkg" / "phases"
    b = tmp_path / "src" / "pkg" / "ui"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    long = a / "thing.py"
    long.write_text("\n".join(f"line {i}" for i in range(1, 201)))
    short = b / "thing.py"
    short.write_text("\n".join(f"line {i}" for i in range(1, 21)))
    other = a / "piezo.py"
    other.write_text(
        "\n".join(
            ["import x", "", "class Piezo:", "    def enable_feedback(self):"]
            + [f"        pass  # {i}" for i in range(5, 60)]
        )
    )
    return [long, short, other]


def _cite(tmp_path, text):
    doc = tmp_path / "note.md"
    doc.write_text(text)
    return [doc]


def test_resolve_matches_on_path_suffix(tree):
    assert len(resolve("thing.py", tree)) == 2
    assert len(resolve("phases/thing.py", tree)) == 1
    assert resolve("nope.py", tree) == []


def test_collect_pairs_symbol_with_its_location(tmp_path, tree):
    docs = _cite(tmp_path, "see enable_feedback(), piezo.py:4 for the mode")
    citations, _ = collect(docs, tree)
    assert len(citations) == 1
    assert citations[0]["symbol"] == "enable_feedback()"
    assert citations[0]["start"] == 4


def test_bare_citation_has_no_symbol(tmp_path, tree):
    docs = _cite(tmp_path, "the guard lives at piezo.py:4")
    citations, _ = collect(docs, tree)
    assert citations[0]["symbol"] is None


@pytest.mark.parametrize(
    "text,expect_found",
    [
        ("enable_feedback(), piezo.py:4", True),
        ("enable_feedback(), piezo.py:50", False),
        ("MODECTRL/enable_feedback, piezo.py:4", True),
        ("Piezo.enable_feedback, piezo.py:4", True),
    ],
)
def test_symbol_proximity(tmp_path, tree, text, expect_found):
    """Drift is a symbol that is no longer near the line it was cited at."""
    citations, sources = collect(_cite(tmp_path, text), tree)
    c = citations[0]
    path = resolve(c["path"], sources)[0]
    assert symbol_near(path, c["start"], c["end"], c["symbol"]) is expect_found


def test_out_of_bounds_line_is_detectable(tmp_path, tree):
    citations, sources = collect(_cite(tmp_path, "ui/thing.py:500"), tree)
    path = resolve(citations[0]["path"], sources)[0]
    length = len(path.read_text().split("\n"))
    assert citations[0]["start"] > length


@pytest.mark.parametrize("text", ["thing.py:10", "thing.py:150"])
def test_bare_basename_is_ambiguous_whatever_the_line(tmp_path, tree, text):
    """Both copies are named `thing.py`, so a path prefix is required.

    Line 10 exists in both. Line 150 exists only in the 200-line copy, which
    makes it resolvable by elimination rather than unambiguous — the check
    asks for the prefix either way.
    """
    citations, sources = collect(_cite(tmp_path, text), tree)
    assert len(resolve(citations[0]["path"], sources)) == 2
    assert unambiguous(citations, sources) == []


def test_path_qualified_citation_resolves_to_one_file(tmp_path, tree):
    citations, sources = collect(_cite(tmp_path, "phases/thing.py:150"), tree)
    pairs = unambiguous(citations, sources)
    assert len(pairs) == 1
    assert pairs[0][1].parts[-2:] == ("phases", "thing.py")


def test_ambiguous_citation_is_not_also_reported_out_of_bounds(tmp_path, tree):
    """One missing prefix is one failure, not two.

    `thing.py:150` is past the end of the 20-line copy, but that is a
    consequence of the ambiguity, not a separate defect.
    """
    citations, sources = collect(_cite(tmp_path, "thing.py:150"), tree)
    assert unambiguous(citations, sources) == []

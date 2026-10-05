"""Check that source citations in prose still point at what they claim.

Docs and comments in this repo cite the source so a reader can check a claim
instead of taking it on faith. A citation names a definition, optionally with a
quoted snippet from inside it:

    <span class="cite">piezo.py::Piezo.feedback_setpoint_pv</span>
    <span class="cite">cavity.py::Cavity._auto_tune “if est_steps == 0:”</span>
    <span class="cite">linac_utils.py “very rough values”</span>

`file.py::Name` names a module-level function, class or assignment.
`Class.name` also covers methods, class attributes and `self.name = ...`
assignments in any method. The snippet must appear, whitespace-normalized,
inside that definition's source, or anywhere in the file when no name is given.

Why not line numbers. This file used to check `file.py:NNN`, and #288 cited
about 80 places that way. On 2026-10-02, #284, #294 and #311 each passed CI and then
merged after #288. They moved lines it cited and broke main's Release run. The
six-line symbol window also hid drift that had already happened: #303's
five-line shift, and a `TUNE_CONFIG` citation 60 lines away from the
constants. A name does not move when lines are added above it. A snippet fails
only when the cited code itself changes, which is when the prose needs
re-reading anyway. The cost: a citation without a snippet points at a whole
function rather than a line. Add a snippet when the line matters.

Line-number citations are now rejected outright, so they cannot creep back.

A path may be partial. This repo has colliding basenames, so the citation needs
enough path to pick exactly one file (`phases/frequency_tuning.py`).
"""

import ast
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

_PATH = r"((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_]+\.py)"

# `foo.py::Name`, `a/foo.py::Class.attr`, either one followed by a quoted
# snippet, or `foo.py “snippet”` on its own. A bare `foo.py` is a mention, not
# a citation, and is not matched.
CITATION = re.compile(
    r"\b" + _PATH + r"(?:::([A-Za-z_][A-Za-z0-9_.]*))?" r"(?:\s+“([^”]+)”)?"
)

# The retired form: `foo.py:12`, `foo.py:12-34`.
LINE_CITATION = re.compile(r"\b" + _PATH + r":(\d+)(?:-(\d+))?\b")


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


def _squash(text):
    return " ".join(text.split())


def resolve(cited_path, sources):
    """Every source file whose path ends with `cited_path`.

    Suffix matching so a citation can be as specific as it needs to be:
    `frequency_tuning.py` matches both copies, `phases/frequency_tuning.py`
    matches one.
    """
    wanted = tuple(cited_path.split("/"))
    return [p for p in sources if tuple(p.parts[-len(wanted) :]) == wanted]


def _add(found, name, node):
    start = min(
        [d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno]
    )
    found.setdefault(name, []).append((start, node.end_lineno))


def _assign_targets(node):
    if isinstance(node, ast.Assign):
        return node.targets
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    return []


def _add_self_attributes(found, func, cls):
    """`self.x = ...` anywhere in `func` defines `cls.x`."""
    for node in ast.walk(func):
        for t in _assign_targets(node):
            if (
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id == "self"
            ):
                _add(found, f"{cls}.{t.attr}", node)


def _walk(found, scope, prefix, cls):
    for node in ast.iter_child_nodes(scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _add(found, prefix + node.name, node)
            if cls:
                _add_self_attributes(found, node, cls)
        elif isinstance(node, ast.ClassDef):
            name = prefix + node.name
            _add(found, name, node)
            _walk(found, node, name + ".", name)
        else:
            for t in _assign_targets(node):
                if isinstance(t, ast.Name):
                    _add(found, prefix + t.id, node)


def definitions(path):
    """Map each citable name in `path` to the (start, end) lines defining it.

    A name can map to several spans: a property and its setter, or a
    `self.x` assigned in more than one method.
    """
    found = {}
    _walk(found, ast.parse(path.read_text(errors="replace")), "", None)
    return found


def collect(targets=None, sources=None):
    """Every citation found, as dicts of origin, path, symbol and snippet."""
    targets = _scan_targets() if targets is None else targets
    sources = _source_files() if sources is None else sources
    found = []
    for target in targets:
        text = target.read_text(errors="replace")
        for m in CITATION.finditer(text):
            if not (m.group(2) or m.group(3)):
                continue
            found.append(
                {
                    "origin": _label(target),
                    "path": m.group(1),
                    "symbol": m.group(2),
                    "snippet": _squash(m.group(3)) if m.group(3) else None,
                }
            )
    return found, sources


def _describe(c):
    out = f"{c['origin']} cites {c['path']}"
    if c["symbol"]:
        out += f"::{c['symbol']}"
    if c["snippet"]:
        out += f" “{c['snippet']}”"
    return out


def unambiguous(citations, sources):
    """Pair each citation that resolves to exactly one file with that file.

    The symbol and snippet checks run only against these. A citation matching
    several files belongs to the ambiguity check, and running the other checks
    on it reports one root cause once per candidate.
    """
    pairs = []
    for c in citations:
        matches = resolve(c["path"], sources)
        if len(matches) == 1:
            pairs.append((c, matches[0]))
    return pairs


def check(citation, path):
    """Why `citation` no longer holds against `path`, or None if it does."""
    lines = path.read_text(errors="replace").split("\n")
    if citation["symbol"]:
        spans = definitions(path).get(citation["symbol"])
        if not spans:
            return f"{citation['symbol']!r} is not defined in {_label(path)}"
    else:
        spans = [(1, len(lines))]
    if citation["snippet"]:
        bodies = (_squash("\n".join(lines[a - 1 : b])) for a, b in spans)
        if not any(citation["snippet"] in body for body in bodies):
            where = citation["symbol"] or _label(path)
            return f"the snippet is no longer in {where}"
    return None


def test_cited_files_exist():
    """A citation naming a file that is not in the tree is stale on its face."""
    citations, sources = collect()
    missing = [c for c in citations if not resolve(c["path"], sources)]
    assert not missing, "citations naming no existing file:\n" + "\n".join(
        f"  {_describe(c)}" for c in missing
    )


def test_ambiguous_citations_are_path_qualified():
    """A bare basename matching two source files does not identify one."""
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


def test_citations_still_hold():
    """The named definition exists and still contains the quoted snippet."""
    citations, sources = collect()
    broken = []
    for c, path in unambiguous(citations, sources):
        reason = check(c, path)
        if reason:
            broken.append(f"  {_describe(c)} — {reason}")
    assert not broken, "citations that no longer hold:\n" + "\n".join(broken)


def test_no_line_number_citations():
    """`file.py:NNN` breaks whenever lines move. See the module docstring."""
    found = []
    for target in _scan_targets():
        text = target.read_text(errors="replace")
        for m in LINE_CITATION.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            found.append(f"  {_label(target)}:{line} — {m.group(0)}")
    assert not found, (
        "line-number citations; cite `file.py::Name` and quote the line "
        "instead:\n" + "\n".join(found)
    )


# ---------------------------------------------------------------------------
# The checks, against fixtures
#
# The scans above pass while nothing in the tree is cited, so they cannot show
# that the logic works. These can.
# ---------------------------------------------------------------------------

PIEZO_SOURCE = """\
LIMIT = 70


class Piezo:
    mode: int = 0

    def __init__(self):
        self.setpoint_pv = "INTEG_SP"

    @property
    def voltage(self):
        # read the drive voltage
        return 25

    @voltage.setter
    def voltage(self, value):
        self.written = value


def helper():
    return LIMIT
"""


@pytest.fixture
def tree(tmp_path):
    """A miniature source tree with a basename collision in it."""
    a = tmp_path / "src" / "pkg" / "phases"
    b = tmp_path / "src" / "pkg" / "ui"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "thing.py").write_text("def run():\n    return 1\n")
    (b / "thing.py").write_text("def run():\n    return 2\n")
    (a / "piezo.py").write_text(PIEZO_SOURCE)
    return sorted((tmp_path / "src").rglob("*.py"))


def _cite(tmp_path, text):
    doc = tmp_path / "note.md"
    doc.write_text(text)
    return [doc]


def _one(tmp_path, tree, text):
    citations, sources = collect(_cite(tmp_path, text), tree)
    assert len(citations) == 1, citations
    c = citations[0]
    return c, resolve(c["path"], sources)


def test_resolve_matches_on_path_suffix(tree):
    assert len(resolve("thing.py", tree)) == 2
    assert len(resolve("phases/thing.py", tree)) == 1
    assert resolve("nope.py", tree) == []


def test_collect_reads_symbol_and_snippet(tmp_path, tree):
    c, _ = _one(
        tmp_path, tree, "see piezo.py::Piezo.voltage “drive\n  voltage”."
    )
    assert c["path"] == "piezo.py"
    assert c["symbol"] == "Piezo.voltage"
    assert c["snippet"] == "drive voltage"


def test_bare_file_mention_is_not_a_citation(tmp_path, tree):
    citations, _ = collect(_cite(tmp_path, "edit piezo.py and rerun"), tree)
    assert citations == []


@pytest.mark.parametrize(
    "symbol",
    [
        "LIMIT",
        "helper",
        "Piezo",
        "Piezo.mode",
        "Piezo.__init__",
        "Piezo.setpoint_pv",
        "Piezo.voltage",
        "Piezo.written",
    ],
)
def test_definition_kinds_are_citable(tmp_path, tree, symbol):
    c, [path] = _one(tmp_path, tree, f"piezo.py::{symbol}")
    assert check(c, path) is None


@pytest.mark.parametrize("symbol", ["Piezo.missing", "voltage", "Other"])
def test_undefined_symbol_is_reported(tmp_path, tree, symbol):
    c, [path] = _one(tmp_path, tree, f"piezo.py::{symbol}")
    assert "is not defined" in check(c, path)


def test_snippet_is_searched_only_inside_the_named_definition(tmp_path, tree):
    """`return LIMIT` is in helper, so it does not hold for Piezo.voltage."""
    c, [path] = _one(tmp_path, tree, "piezo.py::helper “return LIMIT”")
    assert check(c, path) is None
    c, [path] = _one(tmp_path, tree, "piezo.py::Piezo.voltage “return LIMIT”")
    assert "no longer in" in check(c, path)


def test_snippet_matches_any_span_of_a_name(tmp_path, tree):
    """Piezo.voltage is both the getter and the setter."""
    c, [path] = _one(
        tmp_path, tree, "piezo.py::Piezo.voltage “self.written = value”"
    )
    assert check(c, path) is None


def test_file_only_snippet_searches_the_whole_file(tmp_path, tree):
    c, [path] = _one(tmp_path, tree, "piezo.py “LIMIT = 70”")
    assert check(c, path) is None


def test_moving_lines_does_not_break_a_citation(tmp_path, tree):
    """The failure that retired line numbers."""
    piezo = next(p for p in tree if p.name == "piezo.py")
    c, [path] = _one(
        tmp_path, tree, "piezo.py::Piezo.voltage “read the drive voltage”"
    )
    piezo.write_text("# added\n" * 40 + PIEZO_SOURCE)
    assert check(c, path) is None


def test_bare_basename_is_ambiguous(tmp_path, tree):
    citations, sources = collect(_cite(tmp_path, "thing.py::run"), tree)
    assert len(resolve(citations[0]["path"], sources)) == 2
    assert unambiguous(citations, sources) == []


def test_path_qualified_citation_resolves_to_one_file(tmp_path, tree):
    citations, sources = collect(_cite(tmp_path, "phases/thing.py::run"), tree)
    pairs = unambiguous(citations, sources)
    assert len(pairs) == 1
    assert pairs[0][1].parts[-2:] == ("phases", "thing.py")


@pytest.mark.parametrize(
    "text", ["piezo.py:41", "phases/thing.py:10-20", "see thing.py:3."]
)
def test_line_citation_pattern_catches_the_retired_form(text):
    assert LINE_CITATION.search(text)


@pytest.mark.parametrize(
    "text", ["piezo.py::Piezo", "a 3:1 ratio", "piezo.py “x:1”"]
)
def test_line_citation_pattern_ignores_the_new_form(text):
    assert not LINE_CITATION.search(text)

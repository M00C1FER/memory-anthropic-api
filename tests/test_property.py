"""Hypothesis property-based tests for the 6-op contract.

These tests use property-based testing to explore the input space more
broadly than hand-crafted examples allow.  They check invariants that must
hold for ALL valid inputs, not just the ones the author thought of.

Each test creates its own temporary directory inside the test body so that
hypothesis can reset state between generated examples without triggering the
function_scoped_fixture health-check warning.
"""
from __future__ import annotations

import tempfile

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from memory_tool_conformance import FilesystemMemory

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid path segments: non-empty, no slashes, no NUL bytes, not "." or ".."
_SEGMENT = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="/\x00",
    ),
    min_size=1,
    max_size=20,
).filter(lambda s: s not in (".", "..") and s.strip() != "")

_VPATH = st.builds(
    lambda segs: "/memories/" + "/".join(segs),
    st.lists(_SEGMENT, min_size=1, max_size=3),
)

# Arbitrary file content
_CONTENT = st.text(max_size=200)

# Non-empty content (useful as needle for str_replace)
_NONEMPTY = st.text(min_size=1, max_size=50)

# All characters that Python's splitlines() treats as line-separators.
# These must be excluded from _LINE so that insert's splitlines()-based
# counting stays consistent with the test's split("\n") counting.
_SPLITLINES_CHARS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029\x00"

# Non-empty, single-line text: excludes NUL, surrogates, and all splitlines separators.
_LINE = st.text(
    min_size=1,
    max_size=40,
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters=_SPLITLINES_CHARS,
    ),
)

_SETTINGS = dict(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)


def _make_mem():
    td = tempfile.TemporaryDirectory()
    return FilesystemMemory(root=td.name), td


# ---------------------------------------------------------------------------
# create / view round-trip
# ---------------------------------------------------------------------------


@given(path=_VPATH, content=_CONTENT)
@settings(**_SETTINGS)
def test_prop_create_view_roundtrip(path, content):
    """Whatever content we create, view must return it unchanged."""
    m, td = _make_mem()
    with td:
        m.create(path, content)
        assert m.view(path) == content


@given(path=_VPATH, first=_CONTENT, second=_CONTENT)
@settings(**_SETTINGS)
def test_prop_create_overwrite(path, first, second):
    """Creating the same path twice must leave only the second content."""
    m, td = _make_mem()
    with td:
        m.create(path, first)
        m.create(path, second)
        assert m.view(path) == second


# ---------------------------------------------------------------------------
# str_replace
# ---------------------------------------------------------------------------


@given(
    path=_VPATH,
    prefix=_CONTENT,
    needle=_NONEMPTY,
    suffix=_CONTENT,
    replacement=_CONTENT,
)
@settings(**_SETTINGS)
def test_prop_str_replace_replaces_first(path, prefix, needle, suffix, replacement):
    """str_replace replaces exactly the first occurrence of needle."""
    content = prefix + needle + suffix
    # Ensure needle first occurs at exactly len(prefix) in the combined string.
    assume(content.find(needle) == len(prefix))
    m, td = _make_mem()
    with td:
        m.create(path, content)
        m.str_replace(path, needle, replacement)
        result = m.view(path)
        expected = prefix + replacement + suffix
        assert result == expected


@given(path=_VPATH, content=_CONTENT, missing=_NONEMPTY)
@settings(**_SETTINGS)
def test_prop_str_replace_missing_raises(path, content, missing):
    """str_replace must raise ValueError when old_str is not in the file."""
    assume(missing not in content)
    m, td = _make_mem()
    with td:
        m.create(path, content)
        with pytest.raises(ValueError):
            m.str_replace(path, missing, "anything")


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


@given(
    path=_VPATH,
    lines=st.lists(_LINE, min_size=1, max_size=10),
    new_line=_LINE,
    pos=st.integers(min_value=1),
)
@settings(**_SETTINGS)
def test_prop_insert_after_line(path, lines, new_line, pos):
    """Inserting after line N yields a file with exactly one more line."""
    content = "\n".join(lines)
    m, td = _make_mem()
    with td:
        m.create(path, content)
        count_before = len(m.view(path).split("\n"))
        m.insert(path, pos, new_line)
        count_after = len(m.view(path).split("\n"))
        assert count_after == count_before + 1


@given(path=_VPATH, lines=st.lists(_LINE, min_size=1, max_size=10), new_line=_LINE)
@settings(**_SETTINGS)
def test_prop_insert_head_prepends(path, lines, new_line):
    """insert_line=0 places new_line as the very first line."""
    content = "\n".join(lines)
    m, td = _make_mem()
    with td:
        m.create(path, content)
        m.insert(path, 0, new_line)
        result = m.view(path)
        assert result.split("\n")[0] == new_line


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@given(path=_VPATH, content=_CONTENT)
@settings(**_SETTINGS)
def test_prop_delete_removes_file(path, content):
    """After delete, view must raise FileNotFoundError."""
    m, td = _make_mem()
    with td:
        m.create(path, content)
        m.delete(path)
        with pytest.raises(FileNotFoundError):
            m.view(path)


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------


@given(
    src=_VPATH,
    content=_CONTENT,
    dst_segs=st.lists(_SEGMENT, min_size=1, max_size=3),
)
@settings(**_SETTINGS)
def test_prop_rename_moves_content(src, content, dst_segs):
    """rename must move content to the destination and remove the source."""
    dst = "/memories/renamed/" + "/".join(dst_segs)
    assume(src != dst)
    m, td = _make_mem()
    with td:
        m.create(src, content)
        try:
            m.rename(src, dst)
        except FileExistsError:
            return  # dst collided — skip this example
        assert m.view(dst) == content
        with pytest.raises(FileNotFoundError):
            m.view(src)


# ---------------------------------------------------------------------------
# view_range
# ---------------------------------------------------------------------------


@given(
    path=_VPATH,
    lines=st.lists(_LINE, min_size=1, max_size=20),
    start=st.integers(min_value=1, max_value=20),
    end=st.integers(min_value=1, max_value=20),
)
@settings(**_SETTINGS)
def test_prop_view_range_slice(path, lines, start, end):
    """view_range [s, e] returns lines[s-1:e] joined by newlines."""
    assume(start <= end)
    content = "\n".join(lines)
    m, td = _make_mem()
    with td:
        m.create(path, content)
        result = m.view(path, view_range=[start, end])
        expected = "\n".join(lines[start - 1 : end])
        assert result == expected

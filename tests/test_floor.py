import contextlib
import os
import signal
from collections.abc import Generator
from pathlib import Path
from types import FrameType

import pytest

from distiller import floor, messages

# Each test writes its own floor configuration in tmp_path, or hands matches and
# floor_hits patterns and paths, and watches floor from outside: what
# read_floor, matches and floor_hits return or raise, and what the
# configuration holds after.

# How long a call may run before fails_if_it_blocks stops it.
BLOCKING_SECONDS = 5

# The floor configuration's path as a command line could give it, from the
# working directory, which the floor_config fixture sets to tmp_path. A
# rejection names it exactly, ./ included.
FLOOR_CONFIG = "./ci/floor.txt"

# What read_floor raises for a configuration that cannot be read: its reason,
# input, subject and line number, which only an invalid pattern sets.
UNREADABLE = ("unusable-input", "floor", FLOOR_CONFIG, None)

# The default patterns, in the SPEC's order.
SPEC_DEFAULT_PATTERNS = (
    "**/config/**",
    "**/migrations/**",
    "**/poetry.lock",
    "**/uv.lock",
    "**/Pipfile.lock",
    "**/requirements*.txt",
    "**/requirements/**",
    "**/pyproject.toml",
    "**/setup.py",
    "**/setup.cfg",
    "**/pytest.ini",
    "**/tox.ini",
)

# Selection 5's floor: the default patterns and the data/** that its
# configuration adds.
SELECTION_5_PATTERNS = (*SPEC_DEFAULT_PATTERNS, "data/**")

# The byte order mark that a file saved as UTF-8 can start with, and the
# character it decodes to, written by its code point.
BOM = b"\xef\xbb\xbf"
BOM_CHARACTER = chr(0xFEFF)

# Edge 5's path, with a space and an n with a tilde, written by its code point.
TARIFA = "src/shop/tarifa a" + chr(0xF1) + "o.py"

# The characters besides \n at which str.splitlines() splits a line, none of
# which ends a line of the configuration (Rule 9). Those beyond Latin-1 are
# written by code point.
OTHER_LINE_BREAKS = {
    "\r": "a carriage return alone",
    "\x0b": "a line tabulation",
    "\x0c": "a form feed",
    "\x1c": "a file separator",
    "\x1d": "a group separator",
    "\x1e": "a record separator",
    "\x85": "a next line",
    chr(0x2028): "a line separator",
    chr(0x2029): "a paragraph separator",
}

# The whitespace besides spaces and tabs that str.strip() drops, which stays at
# either end of a pattern (Rule 9).
OTHER_WHITESPACE = {
    "\x0b": "a line tabulation",
    "\x0c": "a form feed",
    "\x1c": "a file separator",
    "\x1d": "a group separator",
    "\x1e": "a record separator",
    "\x1f": "a unit separator",
    "\x85": "a next line",
    "\xa0": "a no-break space",
    chr(0x2003): "an em space",
    chr(0x3000): "an ideographic space",
}


class BlockedError(BaseException):
    """A call was still running when the alarm went off.

    A BaseException, so that no `except Exception` in the code under test
    catches it.
    """


@contextlib.contextmanager
def fails_if_it_blocks() -> Generator[None]:
    """Stop with BlockedError a call that blocks, so that the test fails.

    Opening a FIFO for reading waits until something opens it for writing,
    which nothing does here: without the alarm, the test would hang.
    """

    def interrupt(_signal_number: int, _frame: FrameType | None) -> None:
        raise BlockedError

    previous = signal.signal(signal.SIGALRM, interrupt)
    signal.alarm(BLOCKING_SECONDS)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture
def floor_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The file that FLOOR_CONFIG names, with tmp_path as the working directory.

    Nothing is there yet: each test puts there what it needs.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ci").mkdir()
    return tmp_path / "ci" / "floor.txt"


def added_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    """The patterns after the default ones, which read_floor gives first."""
    defaults = floor.DEFAULT_PATTERNS
    assert patterns[: len(defaults)] == defaults
    return patterns[len(defaults) :]


def patterns_added_by(data: bytes, floor_config: Path) -> tuple[str, ...]:
    """The patterns that a configuration holding data adds to the defaults."""
    floor_config.write_bytes(data)
    return added_patterns(floor.read_floor(FLOOR_CONFIG))


def rejection(path: str) -> tuple[str, str, str, int | None]:
    """The reason, input, subject and line number of what read_floor raises."""
    with pytest.raises(messages.Rejected) as caught:
        floor.read_floor(path)
    error = caught.value
    return error.reason, error.input_name, error.subject, error.line_number


def invalid_pattern_at(line_number: int) -> tuple[str, str, str, int | None]:
    """What rejection gives for an invalid pattern at that line of FLOOR_CONFIG."""
    return ("unusable-input", "floor", FLOOR_CONFIG, line_number)


# The default patterns


def test_with_no_configuration_the_floor_is_the_default_patterns() -> None:
    patterns = floor.read_floor(None)

    assert sorted(patterns) == sorted(SPEC_DEFAULT_PATTERNS)


def test_default_patterns_is_what_read_floor_gives_with_no_configuration() -> None:
    patterns = floor.read_floor(None)

    assert patterns == floor.DEFAULT_PATTERNS


def test_a_configuration_adds_its_patterns_after_the_defaults_in_its_order(
    floor_config: Path,
) -> None:
    added = patterns_added_by(b"db/*.sql\ndata/**\ndocs/notes.txt\n", floor_config)

    assert added == ("db/*.sql", "data/**", "docs/notes.txt")


def test_a_configuration_removes_no_default_pattern(floor_config: Path) -> None:
    # Selection 6's configuration and path: the configuration adds data/**, and
    # the default pattern that migrations/0002_vat.py matches is still there.
    floor_config.write_bytes(b"data/**\n")

    patterns = floor.read_floor(FLOOR_CONFIG)

    assert floor.floor_hits(patterns, ["migrations/0002_vat.py"]) == [
        ("**/migrations/**", "migrations/0002_vat.py")
    ]


def test_a_line_that_gitignore_reads_as_a_negation_only_adds_a_pattern(
    floor_config: Path,
) -> None:
    # In a .gitignore, !uv.lock would take uv.lock back out. Here it is one
    # more pattern, and uv.lock still matches **/uv.lock.
    floor_config.write_bytes(b"!uv.lock\n")

    patterns = floor.read_floor(FLOOR_CONFIG)

    assert added_patterns(patterns) == ("!uv.lock",)
    assert floor.floor_hits(patterns, ["uv.lock"]) == [("**/uv.lock", "uv.lock")]


# The configuration's lines


@pytest.mark.parametrize(
    ("data", "added"),
    [
        pytest.param(b"data/**\n", ("data/**",), id="one pattern"),
        pytest.param(b"data/**", ("data/**",), id="a last line without its newline"),
        pytest.param(b"", (), id="an empty file"),
        pytest.param(
            b"data/**\n\n\ndb/*.sql\n", ("data/**", "db/*.sql"), id="blank lines"
        ),
        pytest.param(
            b"# Paths that no test covers\ndata/**\n", ("data/**",), id="a comment"
        ),
        pytest.param(b"#data/**\n", (), id="a pattern commented out"),
        pytest.param(b"#\n", (), id="a # alone"),
        pytest.param(b"# one\n\n# two\n", (), id="only comments and blank lines"),
        pytest.param(
            b"  data/**\t \n", ("data/**",), id="spaces and tabs at either end"
        ),
        pytest.param(b" \t \n", (), id="a line of spaces and tabs, which is blank"),
        pytest.param(b"  # a comment\n", (), id="a comment after spaces"),
        pytest.param(b"\t# a comment\n", (), id="a comment after a tab"),
        pytest.param(
            (TARIFA + "\n").encode(),
            (TARIFA,),
            id="a space and a letter that is not ASCII, inside a pattern",
        ),
        pytest.param(
            b"docs/notes.txt # x\n",
            ("docs/notes.txt # x",),
            id="a # after a pattern, which is part of it",
        ),
        pytest.param(
            "\xa0\n".encode(),
            ("\xa0",),
            id="a line of a no-break space, which is not blank",
        ),
        pytest.param(
            "\xa0# x\n".encode(),
            ("\xa0# x",),
            id="a # after a no-break space, which starts no comment",
        ),
    ],
)
def test_blank_lines_and_comments_are_ignored_and_any_other_line_is_a_pattern(
    data: bytes, added: tuple[str, ...], floor_config: Path
) -> None:
    assert patterns_added_by(data, floor_config) == added


@pytest.mark.parametrize(
    "whitespace",
    [pytest.param(character, id=name) for character, name in OTHER_WHITESPACE.items()],
)
def test_only_spaces_and_tabs_are_dropped_from_either_end_of_a_line(
    whitespace: str, floor_config: Path
) -> None:
    # Rule 9: strip(" \t"), not strip().
    pattern = f"{whitespace}docs/notes.txt{whitespace}"

    added = patterns_added_by(f" \t{pattern}\t \n".encode(), floor_config)

    assert added == (pattern,)


@pytest.mark.parametrize(
    "line_break",
    [pytest.param(character, id=name) for character, name in OTHER_LINE_BREAKS.items()],
)
def test_lines_are_split_on_newline_only(line_break: str, floor_config: Path) -> None:
    # Rule 9: split on \n, not with str.splitlines().
    pattern = f"docs/a{line_break}b.txt"

    added = patterns_added_by(f"{pattern}\n".encode(), floor_config)

    assert added == (pattern,)


@pytest.mark.parametrize(
    ("data", "added"),
    [
        pytest.param(b"docs/notes.txt\r\n", ("docs/notes.txt",), id="a CRLF ending"),
        pytest.param(
            b"docs/notes.txt \t\r\n",
            ("docs/notes.txt",),
            id="a space and a tab before a CRLF ending",
        ),
        pytest.param(
            b"docs/notes.txt\r",
            ("docs/notes.txt",),
            id="a last line that ends in a carriage return",
        ),
        pytest.param(
            b"docs/notes.txt\r\r\n",
            ("docs/notes.txt\r",),
            id="two before the newline, of which one is dropped",
        ),
        pytest.param(
            b"docs/notes.txt\r \n",
            ("docs/notes.txt\r",),
            id="one before a space, so not at the end of its line",
        ),
        pytest.param(
            b"\rdocs/notes.txt\n",
            ("\rdocs/notes.txt",),
            id="one at the start of a line",
        ),
        pytest.param(b"\r\n", (), id="a blank line with a CRLF ending"),
        pytest.param(b"# a comment\r\n", (), id="a comment with a CRLF ending"),
    ],
)
def test_one_carriage_return_at_the_end_of_a_line_is_dropped(
    data: bytes, added: tuple[str, ...], floor_config: Path
) -> None:
    # Rule 9: it is dropped before the spaces and tabs are.
    assert patterns_added_by(data, floor_config) == added


@pytest.mark.parametrize(
    ("data", "added"),
    [
        pytest.param(BOM + b"data/**\n", ("data/**",), id="at the start of the file"),
        pytest.param(BOM, (), id="alone in the file"),
        pytest.param(
            BOM + b"# a comment\ndata/**\n", ("data/**",), id="before a comment"
        ),
        pytest.param(BOM + b"  data/**\n", ("data/**",), id="before spaces"),
        pytest.param(
            b"data/**\n" + BOM + b"docs/notes.txt\n",
            ("data/**", BOM_CHARACTER + "docs/notes.txt"),
            id="at the start of a later line, where it is part of the pattern",
        ),
        pytest.param(
            BOM + BOM + b"data/**\n",
            (BOM_CHARACTER + "data/**",),
            id="a second one after the first, which is part of the pattern",
        ),
    ],
)
def test_a_byte_order_mark_at_the_start_of_the_file_is_ignored(
    data: bytes, added: tuple[str, ...], floor_config: Path
) -> None:
    assert patterns_added_by(data, floor_config) == added


# A configuration as an editor on Windows could save it, line by line.
EDGE_22_LINES = [
    b"# Paths that no test covers",
    b"data/**",
    b"",
    b"  db/*.sql",
    b"\t# migrations are in the floor already",
]


def test_edge_22_a_byte_order_mark_and_crlf_endings_read_like_the_file_without_them(
    floor_config: Path,
) -> None:
    floor_config.write_bytes(BOM + b"\r\n".join(EDGE_22_LINES) + b"\r\n")
    with_them = floor.read_floor(FLOOR_CONFIG)
    floor_config.write_bytes(b"\n".join(EDGE_22_LINES) + b"\n")
    without_them = floor.read_floor(FLOOR_CONFIG)

    assert with_them == without_them
    assert added_patterns(with_them) == ("data/**", "db/*.sql")
    changed = ["data/rates.csv", "db/schema.sql", "src/shop/tax.py"]
    assert sorted(floor.floor_hits(with_them, changed)) == [
        ("data/**", "data/rates.csv"),
        ("db/*.sql", "db/schema.sql"),
    ]


# A configuration that cannot be read


@pytest.mark.usefixtures("floor_config")
def test_k8_a_missing_configuration_cannot_be_read() -> None:
    # Nothing is at the path that FLOOR_CONFIG names.
    assert rejection(FLOOR_CONFIG) == UNREADABLE


def test_k8_a_directory_cannot_be_read(floor_config: Path) -> None:
    floor_config.mkdir()

    assert rejection(FLOOR_CONFIG) == UNREADABLE


def test_k8_a_configuration_the_tool_is_not_allowed_to_read_cannot_be_read(
    floor_config: Path,
) -> None:
    floor_config.write_bytes(b"data/**\n")
    floor_config.chmod(0)
    if os.access(floor_config, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")

    assert rejection(FLOOR_CONFIG) == UNREADABLE


def test_k8_a_fifo_cannot_be_read_and_reading_it_does_not_block(
    floor_config: Path,
) -> None:
    os.mkfifo(floor_config)

    with fails_if_it_blocks():
        found = rejection(FLOOR_CONFIG)

    assert found == UNREADABLE


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"data/\xff.csv\n", id="a byte that UTF-8 never uses"),
        pytest.param(b"data/\x80.csv\n", id="a continuation byte alone"),
        pytest.param((TARIFA + "\n").encode("latin-1"), id="Latin-1"),
        pytest.param(b"data/\xc3.csv\n", id="a sequence cut short inside a line"),
        pytest.param(
            b"data/**\n\xc3", id="a sequence cut short at the end of the file"
        ),
        pytest.param(b"data/\xc0\xaf.csv\n", id="an overlong encoding of /"),
        pytest.param(b"data/\xed\xa0\x80.csv\n", id="an encoded surrogate"),
        pytest.param(b"data/\xf4\x90\x80\x80.csv\n", id="beyond U+10FFFF"),
        pytest.param(
            b"\xff\xfe" + "data/**\n".encode("utf-16-le"),
            id="UTF-16, with its byte order mark",
        ),
        pytest.param(
            b"# tarifa a\xf1o\ndata/**\n", id="a Latin-1 byte, only in a comment"
        ),
    ],
)
def test_k8_a_configuration_that_is_not_valid_utf_8_cannot_be_read(
    data: bytes, floor_config: Path
) -> None:
    floor_config.write_bytes(data)

    assert rejection(FLOOR_CONFIG) == UNREADABLE


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"**.lock\ndata/\xff.csv\n", id="an invalid pattern before"),
        pytest.param(b"data/\xff.csv\n**.lock\n", id="an invalid pattern after"),
    ],
)
def test_k8_a_configuration_that_is_not_utf_8_cannot_be_read_whatever_its_patterns(
    data: bytes, floor_config: Path
) -> None:
    # A file that cannot be read has no line number, even if one of its lines
    # holds an invalid pattern.
    floor_config.write_bytes(data)

    assert rejection(FLOOR_CONFIG) == UNREADABLE


# Invalid patterns

# Edge 21's two patterns, the other ways to write a ?, a [, a ] or a ** inside a
# segment, and what no changed path has: an empty, . or .. segment, or a NUL.
INVALID_PATTERNS = [
    pytest.param("**.lock", id="Edge 21, a ** inside a segment"),
    pytest.param("data/?.csv", id="Edge 21, a ?"),
    pytest.param("data/[ab].csv", id="a character class"),
    pytest.param("data/[.csv", id="a [ alone"),
    pytest.param("data/].csv", id="a ] alone"),
    pytest.param("**/requirements?.txt", id="a ? after a valid **"),
    pytest.param("src/**.py", id="a ** before the rest of a segment"),
    pytest.param("**uv.lock", id="a ** before a name"),
    pytest.param("src/**/test_**.py", id="a ** inside a later segment"),
    pytest.param("data/***", id="three stars"),
    pytest.param("/config/**", id="an empty first segment"),
    pytest.param("config/", id="an empty last segment"),
    pytest.param("a//b", id="an empty segment inside"),
    pytest.param("./config/**", id="a . segment"),
    pytest.param("src/../x", id="a .. segment"),
    pytest.param("data/\x00.csv", id="a NUL"),
]


@pytest.mark.parametrize("pattern", INVALID_PATTERNS)
def test_k8_a_configuration_with_an_invalid_pattern_cannot_be_used(
    pattern: str, floor_config: Path
) -> None:
    floor_config.write_bytes(f"{pattern}\n".encode())

    assert rejection(FLOOR_CONFIG) == invalid_pattern_at(1)


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_k8_a_utf_16_configuration_without_a_byte_order_mark_cannot_be_used(
    encoding: str, floor_config: Path
) -> None:
    # Without its byte order mark, ASCII saved as UTF-16 is valid UTF-8 with a
    # NUL beside each character. The line has no newline: in little-endian, the
    # newline's NUL would start a second line, with a second invalid pattern, and
    # which of two a rejection names is not decided.
    floor_config.write_bytes("docs/notes.txt".encode(encoding))

    assert rejection(FLOOR_CONFIG) == invalid_pattern_at(1)


@pytest.mark.parametrize(
    ("data", "line_number"),
    [
        pytest.param(b"data/**\ndb/*.sql\n**.lock\n", 3, id="after two patterns"),
        pytest.param(
            b"# a comment\n\n**.lock\n", 3, id="after a comment and a blank line"
        ),
        pytest.param(b"data/**\n  **.lock\n", 2, id="after spaces"),
        pytest.param(
            BOM + b"# a comment\r\n\r\n**.lock\r\n",
            3,
            id="with a byte order mark and CRLF endings",
        ),
        pytest.param(b"data/**\n**.lock", 2, id="on a last line without its newline"),
        pytest.param(b"# a comment\n" * 11 + b"**.lock\n", 12, id="at line 12"),
    ],
)
def test_k8_an_invalid_patterns_line_number_counts_every_line_from_1(
    data: bytes, line_number: int, floor_config: Path
) -> None:
    floor_config.write_bytes(data)

    assert rejection(FLOOR_CONFIG) == invalid_pattern_at(line_number)


def test_k8_an_invalid_patterns_line_number_counts_newlines_only(
    floor_config: Path,
) -> None:
    # Rule 9: a line that holds every other character at which
    # str.splitlines() splits is still one line.
    line_breaks = "".join(OTHER_LINE_BREAKS)
    floor_config.write_bytes(f"docs/a{line_breaks}b.txt\n**.lock\n".encode())

    assert rejection(FLOOR_CONFIG) == invalid_pattern_at(2)


def test_a_comment_may_hold_what_would_make_a_pattern_invalid(
    floor_config: Path,
) -> None:
    data = b"# not data/?.csv, data/[ab].csv, /config/** or **.lock\ndata/**\n"

    assert patterns_added_by(data, floor_config) == ("data/**",)


# Patterns as near the invalid ones as a valid pattern gets.
VALID_PATTERNS = [
    pytest.param("**", id="** alone"),
    pytest.param("*", id="* alone"),
    pytest.param("**/**", id="two ** segments"),
    pytest.param("**/*.lock", id="a * after a ** segment"),
    pytest.param("data/*.*", id="two * apart in a segment"),
    pytest.param(".github/**", id="a first segment that starts with a dot"),
    pytest.param("**/.env", id="a last segment that starts with a dot"),
    pytest.param("src/.../x", id="a segment of three dots, which is a name"),
]


@pytest.mark.parametrize("pattern", VALID_PATTERNS)
def test_a_pattern_whose_segments_are_all_valid_is_read(
    pattern: str, floor_config: Path
) -> None:
    assert patterns_added_by(f"{pattern}\n".encode(), floor_config) == (pattern,)


# The configuration, byte for byte


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"# Paths that no test covers\ndata/**\n", id="valid"),
        pytest.param(
            BOM + b"data/**\r\ndb/*.sql\r\n",
            id="Edge 22, a byte order mark and CRLF endings",
        ),
        pytest.param(b"data/**\n**.lock\n", id="an invalid pattern"),
        pytest.param(b"data/\xff.csv\n", id="not UTF-8"),
        pytest.param(b"", id="empty"),
    ],
)
def test_reading_leaves_the_configuration_byte_for_byte_as_it_was(
    data: bytes, floor_config: Path
) -> None:
    floor_config.write_bytes(data)
    os.utime(floor_config, ns=(0, 0))  # an old time, which any write would replace

    with contextlib.suppress(messages.Rejected):
        floor.read_floor(FLOOR_CONFIG)

    assert floor_config.read_bytes() == data
    assert floor_config.stat().st_mtime_ns == 0


def test_a_configuration_that_may_only_be_read_is_read(floor_config: Path) -> None:
    # Rule 3: the floor configuration is opened for reading only, which a
    # read-only file allows.
    floor_config.write_bytes(b"data/**\n")
    floor_config.chmod(0o444)

    assert added_patterns(floor.read_floor(FLOOR_CONFIG)) == ("data/**",)


# Matching

# A pattern and a path that it matches.
MATCHING = [
    pytest.param("**/uv.lock", "uv.lock", id="the SPEC's **/uv.lock, at the root"),
    pytest.param(
        "**/uv.lock",
        "services/billing/uv.lock",
        id="the SPEC's **/uv.lock, deeper, Edge 11's path",
    ),
    pytest.param(
        "config/**", "config/app.yaml", id="the SPEC's config/**, a file in config/"
    ),
    pytest.param(
        "config/**",
        "config/prod/db.yaml",
        id="the SPEC's config/**, a file deeper in config/",
    ),
    pytest.param(
        "**/requirements*.txt",
        "requirements-dev.txt",
        id="the SPEC's **/requirements*.txt",
    ),
    pytest.param(
        "**/requirements/**",
        "requirements/dev.txt",
        id="the SPEC's requirements/dev.txt, through **/requirements/**",
    ),
    pytest.param(
        "**/config/**", "config/app.yaml", id="**/config/**, Edge 20's new name"
    ),
    pytest.param(
        "**/config/**", "src/shop/config/loader.py", id="**/config/**, Edge 10's path"
    ),
    pytest.param(
        "**/requirements/**",
        "requirements/base.txt",
        id="**/requirements/**, Edge 12's path",
    ),
    pytest.param(
        "**/migrations/**",
        "migrations/0002_vat.py",
        id="**/migrations/**, Selection 6's path",
    ),
    pytest.param("data/**", "data/rates.csv", id="Selection 5's pattern and path"),
    pytest.param(
        "**/requirements*.txt", "requirements.txt", id="a * that matches no character"
    ),
    pytest.param("src/**/tax.py", "src/tax.py", id="a ** inside, as no segment"),
    pytest.param("src/**/tax.py", "src/shop/tax.py", id="a ** inside, as one segment"),
    pytest.param(
        "src/**/tax.py", "src/shop/vat/tax.py", id="a ** inside, as two segments"
    ),
    pytest.param("**", "uv.lock", id="** alone, a file at the root"),
    pytest.param("**", "src/shop/tax.py", id="** alone, a file deeper"),
    pytest.param("**/*.lock", "uv.lock", id="**/*.lock, at the root"),
    pytest.param(
        "**/config/**/*.yaml",
        "config/app.yaml",
        id="two ** that do not end the pattern, each as no segment",
    ),
    pytest.param(
        "**/config/*.yaml",
        "config/old/config/app.yaml",
        id="a ** that has to take two segments",
    ),
    pytest.param("*", "uv.lock", id="* alone, a file at the root"),
    pytest.param("*", ".env", id="* alone, a name that starts with a dot"),
    pytest.param("src/*.py", "src/tax.py", id="a * inside a segment"),
    pytest.param("*/uv.lock", "services/uv.lock", id="a * segment"),
    pytest.param(
        "tests/test_*_*.py", "tests/test_tax_vat_rate.py", id="two * in a segment"
    ),
    pytest.param(
        "src/*.py", "src/new" + chr(10) + "line.py", id="a * over a newline in a path"
    ),
    pytest.param(
        "data/*.csv", "data/[2026] rates?.csv", id="a * over a [, a ] and a ? in a path"
    ),
    pytest.param("docs/schema.md", "docs/schema.md", id="no wildcard, the same path"),
    pytest.param(TARIFA, TARIFA, id="a space and a letter that is not ASCII"),
    pytest.param(
        "docs/a+b(1).txt",
        "docs/a+b(1).txt",
        id="characters that a regular expression reads as special",
    ),
    pytest.param("docs/{a,b}.txt", "docs/{a,b}.txt", id="braces"),
    pytest.param("docs/a\\b.txt", "docs/a\\b.txt", id="a backslash"),
    pytest.param("docs/\\*.txt", "docs/\\notes.txt", id="a backslash, then a *"),
    pytest.param(
        "**/config/**",
        ".github/config/labels.yml",
        id="a ** over a directory that starts with a dot",
    ),
]


@pytest.mark.parametrize(("pattern", "path"), MATCHING)
def test_a_pattern_matches_these_paths(pattern: str, path: str) -> None:
    assert floor.matches(pattern, path) is True


# A pattern and a path that it does not match.
NOT_MATCHING = [
    pytest.param("config/**", "config", id="the SPEC's config/**, a file named config"),
    pytest.param(
        "config/**",
        "src/config/app.yaml",
        id="the SPEC's config/**, a config/ that is not at the top",
    ),
    pytest.param(
        "**/requirements*.txt",
        "requirements/dev.txt",
        id="the SPEC's **/requirements*.txt, requirements/dev.txt",
    ),
    pytest.param("data/**", "data", id="a ** that ends the pattern, as no segment"),
    pytest.param("**/config/**", "config", id="**/config/**, a file named config"),
    pytest.param(
        "**/config/**", "src/shop/config", id="**/config/**, a file named config deeper"
    ),
    pytest.param(
        "**/config/**", "configs/app.yaml", id="a directory named config and more"
    ),
    pytest.param("**/config/**", "src/shop/config.py", id="a file named config.py"),
    pytest.param("**/uv.lock", "old-uv.lock", id="a name that ends in uv.lock"),
    pytest.param("**/uv.lock", "uv.lock.bak", id="a name that starts with uv.lock"),
    pytest.param(
        "**/uv.lock", "uv.lock/readme.md", id="a file in a directory named uv.lock"
    ),
    pytest.param("src/*.py", "src/shop/tax.py", id="a * across a /"),
    pytest.param("*", "src/tax.py", id="* alone, a file in a directory"),
    pytest.param("*/uv.lock", "uv.lock", id="a * segment, as no segment"),
    pytest.param("data/*.csv", "data/2026/rates.csv", id="a * across a directory"),
    pytest.param(
        "docs/schema.md", "x/docs/schema.md", id="a pattern starts at the root"
    ),
    pytest.param(
        "docs/schema.md", "docs/schema.md.bak", id="a pattern ends at the path's end"
    ),
    pytest.param(
        "src/**/tax.py", "lib/src/tax.py", id="a ** inside, under another directory"
    ),
    pytest.param(
        "src/**/tax.py",
        "src/shop/vat_tax.py",
        id="a ** inside, a name that ends like the last segment",
    ),
    pytest.param("**/uv.lock", "UV.lock", id="capitals"),
    pytest.param("**/Pipfile.lock", "pipfile.lock", id="lower case"),
    pytest.param("**/config/**", "Config/app.yaml", id="a capital in a directory"),
    pytest.param("**/uv.lock", "uv-lock", id="a . that matches only itself"),
    pytest.param("docs/a+b.txt", "docs/aab.txt", id="a + that matches only itself"),
    pytest.param("docs/{a,b}.txt", "docs/a.txt", id="braces, not expanded"),
    pytest.param(
        TARIFA,
        "src/shop/tarifa ano.py",
        id="a letter that is not ASCII, which matches only itself",
    ),
    pytest.param(
        "docs/a\\b.txt", "docs/ab.txt", id="a backslash that matches only itself"
    ),
    pytest.param(
        "docs/\\*.txt", "docs/*.txt", id="a backslash that makes no * literal"
    ),
    pytest.param("**/uv.lock", "uv.lock" + chr(10), id="a name followed by a newline"),
]


@pytest.mark.parametrize(("pattern", "path"), NOT_MATCHING)
def test_a_pattern_does_not_match_these_paths(pattern: str, path: str) -> None:
    assert floor.matches(pattern, path) is False


# Floor hits

# Patterns, changed paths and the hits they give: each pattern with each
# changed path that it matches.
FLOOR_HITS = [
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["uv.lock"],
        [("**/uv.lock", "uv.lock")],
        id="Selection 4's path",
    ),
    pytest.param(
        SELECTION_5_PATTERNS,
        ["data/rates.csv"],
        [("data/**", "data/rates.csv")],
        id="Selection 5's configuration and path",
    ),
    pytest.param(
        SELECTION_5_PATTERNS,
        ["migrations/0002_vat.py"],
        [("**/migrations/**", "migrations/0002_vat.py")],
        id="Selection 6's configuration and path",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["src/shop/tax.py", "templates/invoice.html"],
        [],
        id="paths that match no pattern",
    ),
    pytest.param(SPEC_DEFAULT_PATTERNS, [], [], id="no changed path"),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["src/shop/config/loader.py"],
        [("**/config/**", "src/shop/config/loader.py")],
        id="Edge 10's path",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["services/billing/uv.lock"],
        [("**/uv.lock", "services/billing/uv.lock")],
        id="Edge 11's path",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["requirements/base.txt"],
        [("**/requirements/**", "requirements/base.txt")],
        id="Edge 12's path",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["settings/app.yaml", "config/app.yaml"],
        [("**/config/**", "config/app.yaml")],
        id="Edge 20's rename, by both its names",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["config/app.yaml", "config/prod/db.yaml"],
        [("**/config/**", "config/app.yaml"), ("**/config/**", "config/prod/db.yaml")],
        id="two paths that match one pattern",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["config/pyproject.toml"],
        [
            ("**/config/**", "config/pyproject.toml"),
            ("**/pyproject.toml", "config/pyproject.toml"),
        ],
        id="a path that matches two patterns",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["requirements/requirements-dev.txt"],
        [
            ("**/requirements*.txt", "requirements/requirements-dev.txt"),
            ("**/requirements/**", "requirements/requirements-dev.txt"),
        ],
        id="a path that both requirements patterns match",
    ),
    pytest.param(
        SPEC_DEFAULT_PATTERNS,
        ["uv.lock", "src/shop/tax.py", "tox.ini"],
        [("**/uv.lock", "uv.lock"), ("**/tox.ini", "tox.ini")],
        id="paths that match among paths that do not",
    ),
]


@pytest.mark.parametrize(("patterns", "changed", "hits"), FLOOR_HITS)
def test_floor_hits_pairs_each_pattern_with_every_changed_path_it_matches(
    patterns: tuple[str, ...], changed: list[str], hits: list[tuple[str, str]]
) -> None:
    found = floor.floor_hits(patterns, changed)

    # Which hits a reason cites, and in what order, is for the selection.
    assert sorted(found) == sorted(hits)

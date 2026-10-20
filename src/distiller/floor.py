from pathlib import Path

from distiller import messages
from distiller.git import RepoPath

# Reads the floor configuration, opening it for reading only, into the default
# patterns and the ones it adds, and matches floor patterns against changed
# paths with the floor's own syntax, not Python's fnmatch.

# The SPEC's default patterns, in its order. A configuration adds patterns
# after them and never removes one.
DEFAULT_PATTERNS: tuple[str, ...] = (
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

# No valid pattern holds one of these: whoever writes ?, [ or ] expects a
# wildcard, and no changed path holds a NUL.
_FORBIDDEN_CHARACTERS = ("?", "[", "]", "\0")

# No changed path has one of these segments, so a pattern with one would
# silently match nothing.
_FORBIDDEN_SEGMENTS = ("", ".", "..")


# The defaults, then the file's; raises Rejected.
def read_floor(path: str | None) -> tuple[str, ...]:
    if path is None:
        return DEFAULT_PATTERNS
    text = _read_text(path)
    return DEFAULT_PATTERNS + _patterns_in(text, path)


def matches(pattern: str, path: RepoPath) -> bool:
    # One /-separated segment at a time, case-sensitively.
    return _segments_match(pattern.split("/"), path.split("/"))


def floor_hits(
    patterns: tuple[str, ...], changed: list[RepoPath]
) -> list[tuple[str, RepoPath]]:
    # Every (pattern, path) pair that matches: the patterns in the order
    # given, and for each one, the changed paths in the order given.
    return [
        (pattern, path)
        for pattern in patterns
        for path in changed
        if matches(pattern, path)
    ]


def _read_text(path: str) -> str:
    data = _read_bytes(path)
    if data is None:
        raise _unusable(path)
    # The whole file is decoded before any line is looked at, so a file that
    # is not valid UTF-8 cannot be read, whatever its lines hold. utf-8-sig
    # drops one byte order mark at the start of the file, and only there.
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # "from None" keeps a traceback from showing the error, whose text
        # quotes the bytes that could not be decoded.
        raise _unusable(path) from None


def _read_bytes(path: str) -> bytes | None:  # None: missing or cannot be read
    # Rule 3: the path must be a regular file before it is opened, since
    # opening a FIFO for reading waits until something opens it for writing.
    # is_file runs os.stat, which follows a symbolic link to what it points to.
    try:
        if not Path(path).is_file():
            return None  # missing, or a directory, a FIFO or a device
        return Path(path).read_bytes()  # opened for reading only
    except OSError:
        return None  # the tool is not allowed to read it, or reading failed


def _patterns_in(text: str, path: str) -> tuple[str, ...]:
    patterns: list[str] = []
    # Rule 9: lines are split on \n only, not with splitlines(), which also
    # splits on \r alone, \v, \f and other characters. Every line counts, from
    # 1, blank lines and comments included.
    for line_number, line in enumerate(text.split("\n"), start=1):
        pattern = _pattern_of(line)
        if pattern is None:
            continue  # a blank line or a comment
        if not _is_valid(pattern):
            raise messages.Rejected(
                reason="unusable-input",
                input_name="floor",
                subject=path,
                line_number=line_number,
            )
        patterns.append(pattern)
    return tuple(patterns)


def _pattern_of(line: str) -> str | None:  # None: a blank line or a comment
    # Rule 9: one \r at the end of the line goes, which a \r\n ending leaves
    # there, and then spaces and tabs at either end, but no other whitespace,
    # which strip() would also drop.
    pattern = line.removesuffix("\r").strip(" \t")
    if pattern == "" or pattern.startswith("#"):
        return None
    return pattern


def _is_valid(pattern: str) -> bool:
    if any(character in pattern for character in _FORBIDDEN_CHARACTERS):
        return False
    return all(_is_valid_segment(segment) for segment in pattern.split("/"))


def _is_valid_segment(segment: str) -> bool:
    if segment in _FORBIDDEN_SEGMENTS:
        return False
    # A ** is valid only as a whole segment: whoever writes **.lock expects it
    # to match at any depth, and inside a segment it could not cross a /.
    return segment == "**" or "**" not in segment


def _segments_match(pattern_segments: list[str], path_segments: list[str]) -> bool:
    if not pattern_segments:
        return not path_segments  # a match only if the path is used up too
    first = pattern_segments[0]
    rest = pattern_segments[1:]
    if first == "**":
        return _double_star_matches(rest, path_segments)
    if not path_segments:
        return False  # a segment of the pattern is left, and none of the path
    return _segment_matches(first, path_segments[0]) and _segments_match(
        rest, path_segments[1:]
    )


def _double_star_matches(rest: list[str], path_segments: list[str]) -> bool:
    # rest: the segments of the pattern after the **.
    if not rest:
        # A ** that ends the pattern matches one or more whole segments.
        return len(path_segments) >= 1
    # Any other ** matches zero or more whole segments: each number of them
    # is tried, from none to all that are left.
    return any(
        _segments_match(rest, path_segments[taken:])
        for taken in range(len(path_segments) + 1)
    )


def _segment_matches(pattern_segment: str, name: str) -> bool:
    # A segment of the pattern other than **, against one segment of the path.
    star = pattern_segment.find("*")
    if star == -1:
        return name == pattern_segment  # every character matches itself
    before = pattern_segment[:star]
    after = pattern_segment[star + 1 :]
    if not name.startswith(before):
        return False
    rest = name[len(before) :]
    # The * matches any run of characters, an empty one included: each length
    # is tried, from none to all that is left.
    return any(_segment_matches(after, rest[taken:]) for taken in range(len(rest) + 1))


def _unusable(path: str) -> messages.Rejected:
    # The floor configuration is missing, cannot be read or is not valid
    # UTF-8. The rejection names it as given on the command line.
    return messages.Rejected(reason="unusable-input", input_name="floor", subject=path)

"""Fail when a text file holds a raw control or invisible character.

A Write or Edit call turns a typed escape into the raw character, and nothing on
screen shows it. This checks every file git tracks, and every untracked one it
does not ignore, so that a new file fails before its commit. A file whose text
attribute .gitattributes unsets, as binary does, is skipped; any other file must
be UTF-8. A finding names the file, the line and the code point, never the
character.
"""

import subprocess
import sys
import unicodedata
from pathlib import Path

# Cc: the C0 controls, DEL and the C1 controls. Cf: the zero-width characters,
# the bidi controls, the BOM, the soft hyphen and the other format characters.
# Zl and Zp: U+2028 and U+2029.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})
ALLOWED = frozenset({"\t", "\n"})


def main() -> int:
    findings: list[str] = []
    for path in text_files():
        findings += check_file(path)
    for finding in findings:
        sys.stdout.write(finding + "\n")
    if not findings:
        return 0
    sys.stdout.write(
        f"{len(findings)} lines hold raw control or invisible characters: "
        "write them as escapes.\n"
    )
    return 1


def text_files() -> list[Path]:
    tracked = git_paths(["ls-files"])
    untracked = git_paths(["ls-files", "--others", "--exclude-standard"])
    binary = binary_paths(tracked + untracked)
    return [
        path
        for path in tracked + untracked
        if path not in binary and is_plain_file(path)
    ]


def git_paths(arguments: list[str]) -> list[Path]:
    output = git([*arguments, "-z"], "")
    return [Path(name) for name in output.split("\0") if name]


def binary_paths(paths: list[Path]) -> set[Path]:
    # check-attr -z answers with three fields per path: path, attribute, value.
    output = git(
        ["check-attr", "-z", "--stdin", "text"],
        "".join(f"{path}\0" for path in paths),
    )
    fields = output.split("\0")
    binary: set[Path] = set()
    for start in range(0, len(fields) - 2, 3):
        if fields[start + 2] == "unset":
            binary.add(Path(fields[start]))
    return binary


def git(arguments: list[str], stdin: str) -> str:
    return subprocess.run(
        ["git", *arguments], input=stdin, capture_output=True, text=True, check=True
    ).stdout


def is_plain_file(path: Path) -> bool:
    # A deleted file is not read, nor a symbolic link, which can point anywhere.
    return path.is_file() and not path.is_symlink()


def check_file(path: Path) -> list[str]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = data[: error.start].count(b"\n") + 1
        return [f"{path}:{line}: not UTF-8; if it is binary, say so in .gitattributes"]
    findings: list[str] = []
    # Lines split on "\n" alone: str.splitlines() also breaks at U+2028 and others.
    for number, line in enumerate(text.split("\n"), start=1):
        codes = forbidden_codes(line)
        if codes:
            findings.append(f"{path}:{number}: {', '.join(codes)}")
    return findings


def forbidden_codes(line: str) -> list[str]:
    codes: list[str] = []
    for character in line:
        if character in ALLOWED:
            continue
        if unicodedata.category(character) not in FORBIDDEN_CATEGORIES:
            continue
        # Controls have no name in the Unicode database.
        name = unicodedata.name(character, "CONTROL")
        code = f"U+{ord(character):04X} {name}"
        if code not in codes:
            codes.append(code)
    return codes


if __name__ == "__main__":
    sys.exit(main())

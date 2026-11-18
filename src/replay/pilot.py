import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

# Reads a pilot's configuration, the TOML file that says how the harness
# replays a project's pull requests. Its keys are the field names of Pilot,
# each one required but floor_config, and each value has its field's type in
# TOML, with no conversion. read_pilot refuses any other file by raising: a
# ValueError that names the file, or, for a path with no file, the OSError of
# opening it. The harness turns either into its exit 1.

# A value as tomllib reads it, but for dates and times, which no field takes
# and which every check below refuses, since their types are none of these.
type _TomlValue = str | int | float | bool | list[_TomlValue] | dict[str, _TomlValue]


@dataclass(frozen=True)
class Pilot:
    project: str
    repository: str
    base_branch: str
    job: str
    python: str
    environment: tuple[tuple[str, ...], ...]  # the commands that build it, in order
    pytest: tuple[str, ...]
    coverage_source: str
    seconds_per_test: int
    adds_timeout_plugin: bool  # poetry's environments lack pytest-timeout
    floor_config: str | None


def read_pilot(path: str) -> Pilot:
    values = _read_toml(path)
    _refuse_unknown_keys(path, values)
    return Pilot(
        project=_read_string(path, values, "project"),
        repository=_read_string(path, values, "repository"),
        base_branch=_read_string(path, values, "base_branch"),
        job=_read_string(path, values, "job"),
        python=_read_string(path, values, "python"),
        environment=_read_commands(path, values, "environment"),
        pytest=_read_strings(path, values, "pytest"),
        coverage_source=_read_string(path, values, "coverage_source"),
        seconds_per_test=_read_integer(path, values, "seconds_per_test"),
        adds_timeout_plugin=_read_boolean(path, values, "adds_timeout_plugin"),
        floor_config=_read_optional_string(path, values, "floor_config"),
    )


def _read_toml(path: str) -> dict[str, _TomlValue]:
    # Opening a path with no file raises its own OSError, which names the path.
    with Path(path).open("rb") as file:
        try:
            return tomllib.load(file)
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            message = f"{path} is not a TOML file: {error}"
            raise ValueError(message) from error


def _refuse_unknown_keys(path: str, values: dict[str, _TomlValue]) -> None:
    # A misspelt key would otherwise leave its field unset, and nobody would see.
    known_keys = [field.name for field in fields(Pilot)]
    for key in values:
        if key not in known_keys:
            message = f"{path}: {key} is not a key of a pilot's configuration"
            raise ValueError(message)


def _required_value(path: str, values: dict[str, _TomlValue], key: str) -> _TomlValue:
    if key not in values:
        message = f"{path}: the key {key} is missing"
        raise ValueError(message)
    return values[key]


def _wrong_type(path: str, key: str, expected: str) -> ValueError:
    return ValueError(f"{path}: the value of {key} must be {expected}")


# The checks below compare type(value), not isinstance: TOML's true and false
# are bools, which Python also takes for ints, since bool is a subclass of int.


def _read_string(path: str, values: dict[str, _TomlValue], key: str) -> str:
    value = _required_value(path, values, key)
    if type(value) is not str:
        raise _wrong_type(path, key, "a string")
    return value


def _read_optional_string(
    path: str, values: dict[str, _TomlValue], key: str
) -> str | None:  # None: the key is left out
    if key not in values:
        return None
    return _read_string(path, values, key)


def _read_integer(path: str, values: dict[str, _TomlValue], key: str) -> int:
    value = _required_value(path, values, key)
    if type(value) is not int:
        raise _wrong_type(path, key, "an integer")
    return value


def _read_boolean(path: str, values: dict[str, _TomlValue], key: str) -> bool:
    value = _required_value(path, values, key)
    if type(value) is not bool:
        raise _wrong_type(path, key, "true or false")
    return value


def _read_strings(
    path: str, values: dict[str, _TomlValue], key: str
) -> tuple[str, ...]:
    strings = _strings_or_none(_required_value(path, values, key))
    if strings is None:
        raise _wrong_type(path, key, "an array of strings")
    return strings


def _read_commands(
    path: str, values: dict[str, _TomlValue], key: str
) -> tuple[tuple[str, ...], ...]:
    value = _required_value(path, values, key)
    expected = "an array of commands, each one an array of strings"
    if type(value) is not list:
        raise _wrong_type(path, key, expected)
    commands: list[tuple[str, ...]] = []
    for item in value:
        command = _strings_or_none(item)
        if command is None:
            raise _wrong_type(path, key, expected)
        commands.append(command)
    return tuple(commands)


def _strings_or_none(value: _TomlValue) -> tuple[str, ...] | None:
    # None: the value is not an array of strings.
    if type(value) is not list:
        return None
    strings: list[str] = []
    for item in value:
        if type(item) is not str:
            return None
        strings.append(item)
    return tuple(strings)

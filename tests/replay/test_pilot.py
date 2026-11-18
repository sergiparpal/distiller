import json
from pathlib import Path

import pytest

from replay import pilot

# Each test writes a pilot's configuration in tmp_path and watches read_pilot
# from outside: the Pilot that it returns, or that it raises. The keys are
# Pilot's field names, floor_config may be left out, a key that Pilot has not
# is refused, and a refusal is an exception of any type, which the harness
# turns into its exit 1: decided by the user on 2026-11-18, for the SPEC. Any
# type but NotImplementedError, which only a stub raises.

# A value as the tests write it into a TOML file.
type TomlValue = str | int | float | bool | list[TomlValue]


def toml_list(items: tuple[str, ...]) -> list[TomlValue]:
    """The strings as a TOML array."""
    return [*items]


def toml_value(value: TomlValue) -> str:
    """The value as a TOML file writes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    return repr(value)


def write_pilot(tmp_path: Path, values: dict[str, TomlValue]) -> str:
    """Write the values as a pilot's configuration, and return its path."""
    path = tmp_path / "pilot.toml"
    lines = [f"{key} = {toml_value(value)}\n" for key, value in values.items()]
    path.write_text("".join(lines), encoding="utf-8")
    return str(path)


def assert_refused(path: str) -> None:
    """read_pilot refuses the configuration: it raises, and not as a stub."""
    with pytest.raises(Exception) as raised:  # noqa: PT011
        pilot.read_pilot(path)
    assert not isinstance(raised.value, NotImplementedError)


# urllib3's environment: the uv sync that its nox session ran all through the
# window, from the commit's own uv.lock.
URLLIB3_SYNC = (
    "uv",
    "sync",
    "--frozen",
    "--python",
    "3.12",
    "--group",
    "dev",
    "--extra",
    "socks",
    "--extra",
    "brotli",
    "--extra",
    "zstd",
    "--extra",
    "h2",
)

# urllib3's nox session's pytest options, without coverage or memray.
URLLIB3_PYTEST = (
    "--strict-config",
    "--strict-markers",
    "--disable-socket",
    "--allow-unix-socket",
    "--allow-hosts=localhost,127.0.0.1,::1,127.0.0.0,240.0.0.0",
)

# poetry's environment, as its CI builds it: the environment, then the install
# from the head's own poetry.lock.
POETRY_ENV_USE = ("poetry", "env", "use", "/usr/bin/python3.12")
POETRY_INSTALL = ("poetry", "install", "--with", "github-actions")

URLLIB3_VALUES: dict[str, TomlValue] = {
    "project": "urllib3",
    "repository": "urllib3/urllib3",
    "base_branch": "main",
    "job": "Ubuntu 3.12",
    "python": "3.12",
    "environment": [toml_list(URLLIB3_SYNC)],
    "pytest": toml_list(URLLIB3_PYTEST),
    "coverage_source": "urllib3",
    "seconds_per_test": 120,
    "adds_timeout_plugin": False,
    "floor_config": "pilots/urllib3-floor.txt",
}

URLLIB3_PILOT = pilot.Pilot(
    project="urllib3",
    repository="urllib3/urllib3",
    base_branch="main",
    job="Ubuntu 3.12",
    python="3.12",
    environment=(URLLIB3_SYNC,),
    pytest=URLLIB3_PYTEST,
    coverage_source="urllib3",
    seconds_per_test=120,
    adds_timeout_plugin=False,
    floor_config="pilots/urllib3-floor.txt",
)

# poetry's: two commands, no pytest option of its own, its pyproject.toml's
# being enough, pytest-timeout added, and no floor_config.
POETRY_VALUES: dict[str, TomlValue] = {
    "project": "poetry",
    "repository": "python-poetry/poetry",
    "base_branch": "main",
    "job": "Ubuntu (Python 3.12) / pytest",
    "python": "3.12",
    "environment": [toml_list(POETRY_ENV_USE), toml_list(POETRY_INSTALL)],
    "pytest": [],
    "coverage_source": "poetry",
    "seconds_per_test": 120,
    "adds_timeout_plugin": True,
}

POETRY_PILOT = pilot.Pilot(
    project="poetry",
    repository="python-poetry/poetry",
    base_branch="main",
    job="Ubuntu (Python 3.12) / pytest",
    python="3.12",
    environment=(POETRY_ENV_USE, POETRY_INSTALL),
    pytest=(),
    coverage_source="poetry",
    seconds_per_test=120,
    adds_timeout_plugin=True,
    floor_config=None,
)

# Every key but floor_config, which may be left out.
REQUIRED_KEYS = tuple(key for key in URLLIB3_VALUES if key != "floor_config")

# A key of urllib3's configuration with a value of another type than its
# field's, by what is wrong with it.
WRONG_TYPES: dict[str, tuple[str, TomlValue]] = {
    "project as a number": ("project", 1),
    "repository as a list": ("repository", ["urllib3/urllib3"]),
    "base_branch as a boolean": ("base_branch", True),
    "job as a number": ("job", 3.12),
    "python as a number, unquoted": ("python", 3.12),
    "environment as a string": ("environment", "uv sync --frozen"),
    "environment as one command, not a list of them": ("environment", ["uv", "sync"]),
    "environment with an argument that is not a string": ("environment", [["uv", 1]]),
    "pytest as a string": ("pytest", "-q"),
    "pytest with an option that is not a string": ("pytest", ["-q", 1]),
    "coverage_source as a list": ("coverage_source", ["urllib3"]),
    "seconds_per_test as a string": ("seconds_per_test", "120"),
    "seconds_per_test as a float": ("seconds_per_test", 120.0),
    "seconds_per_test as a boolean": ("seconds_per_test", True),
    "adds_timeout_plugin as a string": ("adds_timeout_plugin", "false"),
    "adds_timeout_plugin as a number": ("adds_timeout_plugin", 0),
    "floor_config as a number": ("floor_config", 1),
    "floor_config as a list": ("floor_config", ["pilots/urllib3-floor.txt"]),
}

# A key that Pilot has not, added to urllib3's configuration, which keeps
# every key it has.
UNKNOWN_KEYS: dict[str, tuple[str, TomlValue]] = {
    "a misspelt key, beside the right one": ("seconds_per_tests", 120),
    "a key that no field names": ("network", False),
}


@pytest.mark.parametrize(
    ("values", "expected"),
    [(URLLIB3_VALUES, URLLIB3_PILOT), (POETRY_VALUES, POETRY_PILOT)],
    ids=["urllib3", "poetry"],
)
def test_a_pilots_configuration_is_read_into_its_pilot(
    tmp_path: Path, values: dict[str, TomlValue], expected: pilot.Pilot
) -> None:
    assert pilot.read_pilot(write_pilot(tmp_path, values)) == expected


def test_a_configuration_with_no_floor_config_reads_as_none(tmp_path: Path) -> None:
    read = pilot.read_pilot(write_pilot(tmp_path, POETRY_VALUES))
    assert read.floor_config is None


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_a_configuration_that_lacks_a_key_is_refused(tmp_path: Path, key: str) -> None:
    values = {name: value for name, value in URLLIB3_VALUES.items() if name != key}
    assert_refused(write_pilot(tmp_path, values))


@pytest.mark.parametrize(
    ("key", "value"), list(WRONG_TYPES.values()), ids=list(WRONG_TYPES)
)
def test_a_value_of_the_wrong_type_is_refused(
    tmp_path: Path, key: str, value: TomlValue
) -> None:
    assert_refused(write_pilot(tmp_path, {**URLLIB3_VALUES, key: value}))


@pytest.mark.parametrize(
    ("key", "value"), list(UNKNOWN_KEYS.values()), ids=list(UNKNOWN_KEYS)
)
def test_a_key_that_pilot_has_not_is_refused(
    tmp_path: Path, key: str, value: TomlValue
) -> None:
    assert_refused(write_pilot(tmp_path, {**URLLIB3_VALUES, key: value}))


def test_a_file_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "pilot.toml"
    path.write_text('project = "urllib3\n', encoding="utf-8")
    assert_refused(str(path))


def test_a_configuration_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    assert_refused(str(tmp_path / "missing.toml"))

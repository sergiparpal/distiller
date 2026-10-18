from dataclasses import dataclass

Pair = tuple[str, str]  # (classname, name)


@dataclass(frozen=True)
class Result:  # one pair in one JUnit file, its test cases merged
    failed: bool  # a case has a failure or an error
    passed: bool  # no case has a failure, an error or a skipped
    time_ms: int  # the cases' times, each rounded half up, summed


@dataclass(frozen=True)
class JUnit:
    results: dict[Pair, Result]
    has_collection_error: bool


def read_junit(path: str) -> bytes | None:  # None: missing or cannot be read
    raise NotImplementedError


def parse_junit(data: bytes, input_name: str, path: str) -> JUnit:  # raises Rejected
    raise NotImplementedError

def unexpected_failure(error_type: type[BaseException]) -> str:
    # The class, never the instance: an error's text can quote what a file holds.
    return f"distiller: unexpected failure: {error_type.__name__}"


# The SPEC names it Rejected, without the Error suffix that N818 asks for.
class Rejected(Exception):  # noqa: N818
    reason: str
    input_name: str
    subject: str
    line_number: int | None

    def __init__(
        self,
        reason: str,
        input_name: str,
        subject: str,
        line_number: int | None = None,
    ) -> None:
        raise NotImplementedError


def rejection(error: Rejected) -> str:
    raise NotImplementedError


def already_recorded(head: str, junit_sha256: str | None) -> str:
    raise NotImplementedError


def not_a_record(path: str, line_number: int) -> str:
    raise NotImplementedError


def unreadable_record_file(path: str) -> str:
    raise NotImplementedError

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
        super().__init__(reason, input_name, subject, line_number)
        self.reason = reason
        self.input_name = input_name
        self.subject = subject
        self.line_number = line_number


# Every message below is built from fixed text and the values it is given:
# paths and commits as given, the run's key and line numbers. Never from an
# error's text or from what a file holds.


def rejection(error: Rejected) -> str:
    return (
        f"distiller: rejected ({error.reason}, input {error.input_name}): "
        f"{why_rejected(error)}"
    )


def why_rejected(error: Rejected) -> str:
    if error.reason == "coverage-not-ancestor":
        return (
            f"the coverage commit {error.subject} is neither "
            "the merge-base nor one of its ancestors"
        )
    if error.reason == "missing-history":
        return f"the checkout {error.subject} is shallow and lacks the history"
    if error.reason == "unsafe-xml":
        return f"{error.subject} declares an XML entity"
    if error.reason == "no-shared-lines":
        return (
            f"no line in {error.subject} was recorded for more than one test: "
            "record the coverage at M with --cov-context=test and "
            "COVERAGE_CORE=ctrace, or the suite's tests share no code"
        )
    if error.reason == "collection-error":
        return f"{error.subject} holds a collection error"
    return why_unusable(error)


def why_unusable(error: Rejected) -> str:
    if error.line_number is not None:
        return (
            f"{error.subject}, line {error.line_number}: the floor pattern is not valid"
        )
    return f"cannot use {error.subject}"


def already_recorded(head: str, junit_sha256: str | None) -> str:
    if junit_sha256 is None:
        junit_sha256 = "null"
    return (
        "distiller: warning: this run is already recorded, "
        f"with head {head} and junit_sha256 {junit_sha256}; nothing appended"
    )


def not_a_record(path: str, line_number: int) -> str:
    return f"distiller: {path}, line {line_number}: not a record"


def unreadable_record_file(path: str) -> str:
    return f"distiller: cannot read the record file {path}: it is missing or unreadable"

from replay.pilot import Pilot


def replay(  # noqa: PLR0913, one argument for each option of the command line
    pilot: Pilot,
    *,
    manifest: str,
    clone: str,
    work: str,
    records: str,
    tool: str,
    only: list[int] | None,
) -> int:
    raise NotImplementedError

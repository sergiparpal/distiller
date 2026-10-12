def unexpected_failure(error_type: type[BaseException]) -> str:
    # The class, never the instance: an error's text can quote what a file holds.
    return f"distiller: unexpected failure: {error_type.__name__}"

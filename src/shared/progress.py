"""Progress log entry helpers: ok, fail, info, warn."""


def ok(message: str) -> dict:
    """Return a success-level progress entry."""
    return {"level": "ok", "message": message}


def fail(message: str) -> dict:
    """Return a failure-level progress entry."""
    return {"level": "fail", "message": message}


def info(message: str) -> dict:
    """Return an info-level progress entry."""
    return {"level": "info", "message": message}


def warn(message: str) -> dict:
    """Return a warning-level progress entry."""
    return {"level": "warn", "message": message}

from urllib.parse import urlsplit

from fastapi import HTTPException


def normalize_origin(value: str | None) -> str | None:
    """Validate and canonicalize a widget's authorized website origin.

    Returns ``None`` for blank input, a ``scheme://host[:port]`` string for a
    valid exact origin, or raises 422 for anything with a path/query/credentials
    or an insecure production scheme. Shared by the settings and site-creation
    routes so both enforce identical rules.
    """
    if value is None or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(status_code=422, detail="Website must be an exact HTTP(S) origin.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise HTTPException(status_code=422, detail="Production widget origins must use HTTPS.")
    return f"{parsed.scheme}://{parsed.netloc.lower()}"

"""Process-local bootstrap credentials; no domain authority is granted here."""
import hmac
import secrets

from lineage.core.errors import LineageError


def new_token() -> str:
    return secrets.token_urlsafe(32)


def authorize(
    *, host: str, origin: str | None, token: str | None,
    expected_authority: str, expected_token: str,
    mutation: bool,
) -> None:
    expected_origin = 'http://' + expected_authority
    if host != expected_authority or (origin is not None and origin != expected_origin):
        raise LineageError('bad_args')
    if mutation:
        if origin != expected_origin or not isinstance(token, str):
            raise LineageError('bad_args')
        try:
            matches = hmac.compare_digest(token, expected_token)
        except (TypeError, ValueError):
            matches = False
        if not matches:
            raise LineageError('bad_args')

"""Supabase JWT verification.

Supports both signing schemes Supabase uses:
- Asymmetric (ES256/RS256): verified against the project's JWKS endpoint,
  fetched once and cached (PyJWT's PyJWKClient handles caching + kid lookup).
- Legacy HS256: verified with SUPABASE_JWT_SECRET.

The token header's `alg` decides which path is taken, so the same code works
on any Supabase project without configuration changes.
"""
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings

_AUDIENCE = "authenticated"


class AuthError(Exception):
    """Raised when a token is missing, malformed, expired, or unverifiable."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str | None


@lru_cache
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(get_settings().jwks_url, cache_keys=True, lifespan=3600)


def verify_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise AuthError("Malformed token") from exc

    alg = header.get("alg")
    try:
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise AuthError("HS256 token but SUPABASE_JWT_SECRET is not set")
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=_AUDIENCE,
            )
        elif alg in ("ES256", "RS256"):
            signing_key = _jwks_client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience=_AUDIENCE,
            )
        else:
            raise AuthError(f"Unsupported token algorithm: {alg}")
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid token") from exc

    sub = claims.get("sub")
    if not sub:
        raise AuthError("Token has no subject")
    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise AuthError("Token subject is not a UUID") from exc

    return AuthenticatedUser(id=user_id, email=claims.get("email"))

"""FastAPI auth dependency — attached to the /api router so every route under
it requires a valid Supabase JWT. Handlers receive the typed user via
`user: CurrentUser`."""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.auth.jwt import AuthenticatedUser, AuthError, verify_token


def get_current_user(request: Request) -> AuthenticatedUser:
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_token(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

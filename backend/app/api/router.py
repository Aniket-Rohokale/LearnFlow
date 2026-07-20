"""Protected API router. The auth dependency is applied here, router-wide:
every route registered under /api requires a valid Supabase JWT. Stage 2
CRUD routers will be include_router()'d onto this same router."""
from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, get_current_user

api_router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


@api_router.get("/me")
async def read_me(user: CurrentUser) -> dict:
    """Stage 1 checkpoint endpoint: 200 with a valid token, 401 without."""
    return {"id": str(user.id), "email": user.email}

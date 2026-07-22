"""Protected API router. The auth dependency is applied here, router-wide:
every route registered under /api requires a valid Supabase JWT."""
from fastapi import APIRouter, Depends

from app.api import (
    activity,
    burnout,
    courses,
    dashboard,
    modules,
    plan,
    profile,
    recommendations,
    roadmap,
)
from app.auth.dependencies import CurrentUser, get_current_user

api_router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

api_router.include_router(profile.router)
api_router.include_router(courses.router)
api_router.include_router(modules.router)
api_router.include_router(activity.router)
api_router.include_router(dashboard.router)
api_router.include_router(recommendations.router)

# Stage 5 — AI features
api_router.include_router(plan.router)
api_router.include_router(burnout.router)
api_router.include_router(roadmap.router)


@api_router.get("/me")
async def read_me(user: CurrentUser) -> dict:
    """Stage 1 checkpoint endpoint: 200 with a valid token, 401 without."""
    return {"id": str(user.id), "email": user.email}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

app = FastAPI(title="TrackAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    """Public liveness probe — the only unauthenticated route."""
    return {"status": "ok"}

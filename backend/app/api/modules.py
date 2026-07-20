from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import Course, Module
from app.schemas.core import ModuleOut, ModuleUpdate
from app.services.progress import recompute_progress

router = APIRouter(prefix="/modules", tags=["modules"])


async def get_owned_module(
    module_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> Module:
    module = (
        await db.execute(
            select(Module)
            .join(Course, Course.id == Module.course_id)
            .where(Module.id == module_id, Course.user_id == user.id)
        )
    ).scalar_one_or_none()
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    return module


@router.patch("/{module_id}", response_model=ModuleOut)
async def update_module(
    payload: ModuleUpdate,
    module: Module = Depends(get_owned_module),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "completed" in data:
        completed = data.pop("completed")
        if completed != module.completed:
            module.completed = completed
            module.completed_at = datetime.now(timezone.utc) if completed else None
    for field, value in data.items():
        setattr(module, field, value)
    await db.flush()
    await recompute_progress(db, module.course_id)
    await db.commit()
    return module


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    module: Module = Depends(get_owned_module), db: AsyncSession = Depends(get_db)
):
    course_id = module.course_id
    await db.delete(module)
    await db.flush()
    await recompute_progress(db, course_id)
    await db.commit()

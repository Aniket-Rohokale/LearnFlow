from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai import parser as syllabus_parser
from app.ai.parser import SyllabusParseError
from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import AIRecommendation, Course, CourseProgress, Module
from app.schemas.core import (
    CourseCreate,
    CourseIngestOut,
    CourseListItem,
    CourseOut,
    CourseUpdate,
    IngestRequest,
    ModuleCreate,
    ModuleOut,
)
from app.services.progress import recompute_progress

router = APIRouter(prefix="/courses", tags=["courses"])


async def get_owned_course(
    course_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> Course:
    """Load a course scoped to the requesting user. A course belonging to
    someone else 404s — indistinguishable from not existing."""
    course = (
        await db.execute(
            select(Course)
            .options(selectinload(Course.modules), selectinload(Course.progress))
            .where(Course.id == course_id, Course.user_id == user.id)
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


def _course_out(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        platform=course.platform,
        title=course.title,
        url=course.url,
        instructor=course.instructor,
        created_at=course.created_at,
        percent_complete=float(course.progress.percent_complete) if course.progress else 0.0,
        last_synced_at=course.progress.last_synced_at if course.progress else None,
        modules=[ModuleOut.model_validate(m) for m in course.modules],
    )


@router.get("", response_model=list[CourseListItem])
async def list_courses(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(
                Course,
                func.coalesce(CourseProgress.percent_complete, 0),
                func.count(Module.id),
                func.count(Module.id).filter(Module.completed.is_(True)),
            )
            .outerjoin(CourseProgress, CourseProgress.course_id == Course.id)
            .outerjoin(Module, Module.course_id == Course.id)
            .where(Course.user_id == user.id)
            .group_by(Course.id, CourseProgress.percent_complete)
            .order_by(Course.created_at.desc())
        )
    ).all()
    return [
        CourseListItem(
            id=c.id,
            platform=c.platform,
            title=c.title,
            url=c.url,
            instructor=c.instructor,
            created_at=c.created_at,
            percent_complete=float(percent),
            module_count=total,
            completed_module_count=done,
        )
        for c, percent, total, done in rows
    ]


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    course = Course(
        user_id=user.id,
        url=str(payload.url),
        title=payload.title,
        platform=payload.platform,
        instructor=payload.instructor,
    )
    db.add(course)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already track a course with this URL"
        )
    await recompute_progress(db, course.id)
    await db.commit()
    return _course_out(await get_owned_course(course.id, user, db))


@router.post("/ingest", response_model=CourseIngestOut, status_code=status.HTTP_200_OK)
async def ingest_course(
    payload: IngestRequest, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    """Extension capture flow: parse the page text with the LLM, then upsert
    on (user_id, url) — re-capturing a course updates it in place instead of
    duplicating it. Completion state is preserved for modules whose title
    survives the re-capture."""
    url = str(payload.url)
    try:
        parsed = await syllabus_parser.parse_syllabus(payload.page_text, url)
    except SyllabusParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    course = (
        await db.execute(
            select(Course)
            .options(selectinload(Course.modules))
            .where(Course.user_id == user.id, Course.url == url)
        )
    ).scalar_one_or_none()
    created = course is None

    if created:
        course = Course(
            user_id=user.id,
            url=url,
            title=parsed.title,
            platform=parsed.platform,
            instructor=parsed.instructor,
        )
        db.add(course)
        await db.flush()
        completed_by_title: dict[str, Module] = {}
    else:
        course.title = parsed.title
        course.platform = parsed.platform
        course.instructor = parsed.instructor
        # Carry completion state across the re-capture by title match, then
        # replace the module set (positions may have shifted on the platform).
        completed_by_title = {m.title: m for m in course.modules if m.completed}
        for module in list(course.modules):
            await db.delete(module)
        await db.flush()  # clear (course_id, position) rows before re-insert

    for position, item in enumerate(parsed.modules):
        old = completed_by_title.get(item.title)
        db.add(
            Module(
                course_id=course.id,
                position=position,
                title=item.title,
                estimated_minutes=item.estimated_minutes,
                completed=old is not None,
                completed_at=old.completed_at if old is not None else None,
            )
        )
    await db.flush()

    # Audit trail: the raw parse is appended to ai_recommendations so the
    # dashboard can show "last synced from AI" provenance.
    db.add(
        AIRecommendation(
            user_id=user.id,
            type="syllabus",
            content_json=parsed.model_dump(),
            model=syllabus_parser.resolved_model(),
        )
    )

    await recompute_progress(db, course.id)
    await db.commit()
    fresh = await get_owned_course(course.id, user, db)
    return CourseIngestOut(created=created, **_course_out(fresh).model_dump())


@router.get("/{course_id}", response_model=CourseOut)
async def read_course(course: Course = Depends(get_owned_course)):
    return _course_out(course)


@router.patch("/{course_id}", response_model=CourseOut)
async def update_course(
    payload: CourseUpdate,
    course: Course = Depends(get_owned_course),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    return _course_out(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course: Course = Depends(get_owned_course), db: AsyncSession = Depends(get_db)
):
    await db.delete(course)  # modules + progress cascade
    await db.commit()


@router.post(
    "/{course_id}/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED
)
async def add_module(
    payload: ModuleCreate,
    course: Course = Depends(get_owned_course),
    db: AsyncSession = Depends(get_db),
):
    next_position = (
        await db.execute(
            select(func.coalesce(func.max(Module.position), -1) + 1).where(
                Module.course_id == course.id
            )
        )
    ).scalar_one()
    module = Module(
        course_id=course.id,
        position=next_position,
        title=payload.title,
        estimated_minutes=payload.estimated_minutes,
    )
    db.add(module)
    await db.flush()
    await recompute_progress(db, course.id)
    await db.commit()
    return module

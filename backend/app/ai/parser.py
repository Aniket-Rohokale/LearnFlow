"""OpenAI-compatible syllabus parser (Stage 3).

Takes raw page text captured by the browser extension and returns a
structured course outline. Uses the API's `response_format` / structured
outputs so the response is guaranteed valid JSON that matches our Pydantic
schema.

Configured for an OpenAI-compatible router via environment variables:
  OPENAI_BASE_URL   — e.g. https://api.openai.com/v1  or your proxy
  OPENAI_API_KEY    — API key (or any token the router accepts)
  OPENAI_MODEL      — optional, defaults to gpt-4o-mini

The call is isolated here so the API layer stays testable:
tests monkeypatch `parse_syllabus` and never touch the network.
"""
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings

# Default model — can be overridden via env var.
DEFAULT_MODEL = "gpt-4o-mini"

# Captured pages can be huge (Udemy course pages exceed 100K chars of DOM
# text). Cap what we send: enough to cover any real syllabus section while
# bounding token spend. The extension already strips scripts/styles.
MAX_PAGE_TEXT_CHARS = 60_000


class ParsedModule(BaseModel):
    title: str = Field(description="Section or lecture title, cleaned of numbering artifacts")
    estimated_minutes: int | None = Field(
        default=None,
        description="Estimated duration in whole minutes if the page states one, else null",
    )


class ParsedSyllabus(BaseModel):
    title: str = Field(description="The course title")
    platform: str = Field(
        description="Learning platform name, e.g. Udemy, Coursera, YouTube, edX"
    )
    instructor: str | None = Field(
        default=None, description="Primary instructor name if present, else null"
    )
    modules: list[ParsedModule] = Field(
        description="Ordered syllabus sections/modules, top-level only"
    )


SYSTEM_PROMPT = """You extract structured course syllabi from raw web page text \
captured by a browser extension.

The text is messy DOM text: navigation, cookie banners, reviews, and footers \
surround the actual course content. Identify the course title, platform, \
instructor, and the ordered list of top-level syllabus sections.

Rules:
- Use top-level sections/modules, not individual sub-lectures, when the page \
has a two-level hierarchy. A course should typically yield 5-30 modules.
- Convert durations to whole minutes (e.g. "2hr 30min" -> 150). If a section \
has no stated duration, use null — never guess.
- Strip numbering prefixes like "Section 4:" from titles.
- Ignore promotional content, reviews, and "related courses" lists.
- If the platform is not obvious from the text, infer it from the page URL.

Respond with a single JSON object, no prose, exactly this shape:
{"title": str, "platform": str, "instructor": str | null,
 "modules": [{"title": str, "estimated_minutes": int | null}, ...]}"""


class SyllabusParseError(Exception):
    """Raised when the model cannot produce a usable syllabus from the page."""


def resolved_model() -> str:
    """Model actually used for parsing — recorded in ai_recommendations."""
    return get_settings().openai_model or DEFAULT_MODEL


async def parse_syllabus(page_text: str, url: str) -> ParsedSyllabus:
    """Parse captured page text into a structured syllabus via the LLM."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise SyllabusParseError("OPENAI_API_KEY is not configured on the server")

    text = page_text[:MAX_PAGE_TEXT_CHARS]
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    model = resolved_model()

    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Page URL: {url}\n\n"
                        f"Captured page text:\n\n{text}"
                    ),
                },
            ],
            # json_object mode: schema is enforced by the prompt + Pydantic
            # validation below — some routers reject strict json_schema mode.
            response_format={"type": "json_object"},
        )
    finally:
        await client.close()

    choice = response.choices[0]
    if choice.finish_reason == "refusal" or choice.finish_reason == "content_filter":
        raise SyllabusParseError("The model declined to process this page")

    raw = choice.message.content
    if raw is None:
        raise SyllabusParseError("No text content in the model response")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SyllabusParseError(f"Invalid JSON from model: {exc}") from exc
    if not data.get("title"):
        raise SyllabusParseError("Could not identify a course on this page")
    try:
        return ParsedSyllabus.model_validate(data)
    except ValidationError as exc:
        raise SyllabusParseError(f"Model response did not match schema: {exc}") from exc

"""Shared LLM utility for AI features (Stage 5).

Wraps an OpenAI-compatible chat-completion call with a single retry on
Pydantic validation failure. All three AI features (plan, burnout, roadmap)
use this so the retry-once + 502 pattern lives in one place.
"""
import json
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
MAX_OUTPUT_TOKENS = 2000


class LLMCallError(Exception):
    """The LLM could not produce a valid response after the retry."""


async def call_llm_with_retry(
    system_prompt: str,
    user_message: str,
    output_model: type[BaseModel],
) -> tuple[BaseModel, str]:
    """Call the LLM with ``response_format="json_object"``, parse the JSON
    response, validate against *output_model*, and retry **once** on
    ``ValidationError``.

    Returns ``(validated_model, model_name)``.

    Raises ``LLMCallError`` on:
    - missing API key
    - model refusal / content filter
    - empty response
    - invalid JSON
    - validation failure after the retry
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMCallError("OPENAI_API_KEY is not configured on the server")

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    model = settings.openai_model or DEFAULT_MODEL

    try:
        return await _attempt(client, model, system_prompt, user_message, output_model, 0)
    finally:
        await client.close()


async def _attempt(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    user_message: str,
    output_model: type[BaseModel],
    attempt: int,
) -> tuple[BaseModel, str]:
    """Internal: make one API call and validate.

    *attempt* is 0 for the first try and 1 for the single retry.
    """
    response = await client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
    )

    choice = response.choices[0]
    if choice.finish_reason in ("refusal", "content_filter"):
        raise LLMCallError("The model declined to process this request")

    raw = choice.message.content
    if raw is None:
        raise LLMCallError("No content in the model response")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMCallError(f"Invalid JSON from model: {exc}") from exc

    try:
        validated = output_model.model_validate(data)
    except ValidationError as exc:
        if attempt == 0:
            logger.warning("LLM output failed validation, retrying once: %s", exc)
            return await _attempt(
                client, model,
                system_prompt,
                user_message + f"\n\nPrevious response failed validation. Errors:\n{exc}\nFix the JSON and retry.",
                output_model,
                attempt + 1,
            )
        logger.error(
            "LLM output still invalid after retry. Raw=%s Errors=%s", raw, exc
        )
        raise LLMCallError("Model returned invalid data after retry") from exc

    return validated, model

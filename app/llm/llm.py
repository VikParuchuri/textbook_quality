import asyncio
import hashlib
import time
from typing import AsyncGenerator, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.db.session import get_session
from app.llm.adaptors.oai import (
    oai_chat_response,
    oai_prompt_response,
    oai_tokenize_prompt,
)
from app.llm.exceptions import GenerationError, InvalidRequestError, RateLimitError
from app.llm.models import Prompt
from app.llm.schemas import GenerationSettings
from app.settings import settings
from app.util import fix_unicode_text


async def generate_response(
    prompt: str,
    prompt_settings: GenerationSettings,
    history: Optional[List] = None,
    max_tries: int = 2,
    cache: bool = True,
) -> AsyncGenerator[str, None]:
    temperature = prompt_settings.temperature
    max_tokens = prompt_settings.max_tokens
    timeout = prompt_settings.timeout
    stop_tokens = prompt_settings.stop_tokens
    prompt_type = prompt_settings.prompt_type
    model = (
        prompt_settings.model or settings.LLM_TYPE
    )  # Use default model if not specified

    # Remove utf-8 surrogate characters
    prompt = fix_unicode_text(prompt)

    # Hash the prompt as a DB key
    hash = hashlib.sha512()
    hash.update(prompt.encode("utf-8"))
    hex = hash.hexdigest()

    async with get_session() as db:
        # Break if we've already run this prompt
        query = await db.exec(
            select(Prompt).where(Prompt.hash == hex, Prompt.model == settings.LLM_TYPE)
        )
        prompt_model = query.first()

    if prompt_model is not None and cache:
        yield prompt_model.response
        return

    orig_model = model
    for i in range(max_tries):
        try:
            match model:
                case "gpt-3.5-turbo" | "gpt-4":
                    prompt_tokens = oai_tokenize_prompt(prompt)

                    # Reduce tokens requested if we have too many in the prompt
                    if (
                        prompt_tokens + max_tokens
                        >= settings.LLM_TYPES[model]["max_tokens"]
                    ):
                        # Use extended model if we have too many tokens
                        model = settings.LLM_EXTENDED_TYPE
                        if (
                            prompt_tokens + max_tokens
                            >= settings.LLM_TYPES[model]["max_tokens"]
                        ):
                            raise InvalidRequestError(
                                f"Input prompt is too long, requested {prompt_tokens} prompt tokens and {max_tokens} generation tokens."
                            )

                    response = oai_chat_response(
                        prompt,
                        temperature,
                        timeout,
                        max_tokens,
                        history,
                        stop_tokens,
                        model=model,
                    )
                case "gpt-3.5-turbo-instruct":
                    prompt_tokens = oai_tokenize_prompt(prompt)
                    if (
                        prompt_tokens + max_tokens
                        >= settings.LLM_TYPES[model]["max_tokens"]
                    ):
                        raise InvalidRequestError(
                            f"Input prompt is too long, requested {prompt_tokens} prompt tokens and {max_tokens} generation tokens."
                        )

                    response = oai_prompt_response(
                        prompt,
                        temperature,
                        timeout,
                        max_tokens,
                        stop_tokens,
                        model=model,
                    )
                case _:
                    if model not in settings.LLM_TYPES:
                        raise NotImplementedError(
                            "This LLM type is not supported currently."
                        )

                    prompt_tokens = oai_tokenize_prompt(prompt)

                    allowed_tokens = settings.LLM_TYPES[model]["max_tokens"]
                    if prompt_tokens + max_tokens > allowed_tokens:
                        max_tokens = allowed_tokens - prompt_tokens

                    if max_tokens < 256:
                        raise InvalidRequestError(
                            f"Input prompt is too long, requested {prompt_tokens} prompt tokens and {max_tokens} generation tokens."
                        )

                    response = oai_prompt_response(
                        prompt,
                        temperature,
                        timeout,
                        max_tokens,
                        stop_tokens,
                        model=model,
                    )
            break
        except (GenerationError, RateLimitError, InvalidRequestError):
            # Re-raise error if we're on the last try
            model = orig_model
            if i == max_tries - 1:
                raise

            await asyncio.sleep(30 * (i + 1))

    full_text = ""
    async for chunk in response:
        text = chunk.text
        response_tokens = chunk.tokens
        yield text
        full_text += text

    # Skip caching
    if not cache:
        return

    async with get_session() as db:
        try:
            prompt_model = Prompt(
                hash=hex,
                prompt=prompt,
                response=full_text,
                type=prompt_type,
                model=settings.LLM_TYPE,
            )
            db.add(prompt_model)
            await db.commit()
        except IntegrityError:
            await db.rollback()

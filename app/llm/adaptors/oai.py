from copy import deepcopy
from typing import AsyncGenerator, List, Optional

import openai
import stopit
import tiktoken
from aiohttp import ClientPayloadError
from openai.error import APIConnectionError, APIError, ServiceUnavailableError, Timeout

from app.llm.exceptions import GenerationError, InvalidRequestError, RateLimitError
from app.llm.schemas import LLMResponse
from app.settings import settings

openai.api_key = settings.OPENAI_KEY
tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
if settings.OPENAI_BASE_URL:
    openai.api_base = settings.OPENAI_BASE_URL


def beginning_of_exception(message: str):
    return message.split(".")[0]


def oai_tokenize_prompt(prompt):
    return len(tokenizer.encode(prompt))


@stopit.threading_timeoutable(default=None)
async def oai_chat_wrapped(
    history: List,
    temperature: float,
    max_tokens: int,
    inner_timeout: int = settings.LLM_TIMEOUT,
    stop_sequences: Optional[List] = None,
    model: str = settings.LLM_TYPE,
) -> AsyncGenerator[str, None]:
    response = await openai.ChatCompletion.acreate(
        model=model,
        messages=history,
        temperature=temperature,
        max_tokens=max_tokens,
        n=1,
        stop=stop_sequences,
        stream=True,
        request_timeout=inner_timeout,
    )
    async for chunk in response:
        stream = chunk
        text = stream["choices"][0]["delta"].get("content", "")
        if text:
            yield text  # Streaming API has the delta property, and the content key inside


@stopit.threading_timeoutable(default=None)
async def oai_prompt_wrapped(
    prompt: str,
    temperature: float,
    max_tokens: int,
    inner_timeout: int = settings.LLM_TIMEOUT,
    stop_sequences: Optional[List] = None,
    model: str = settings.LLM_TYPE,
) -> AsyncGenerator[str, None]:
    response = await openai.Completion.acreate(
        model=model,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        n=1,
        stop=stop_sequences,
        stream=True,
        request_timeout=inner_timeout,
    )
    async for chunk in response:
        stream = chunk
        text = stream["choices"][0]["text"]
        if text:
            yield text  # Streaming API has the delta property, and the content key inside


async def oai_prompt_response(
    prompt: str,
    temperature: float = settings.LLM_TEMPERATURE,
    timeout: int = settings.LLM_TIMEOUT,
    max_tokens: int = settings.LLM_MAX_RESPONSE_TOKENS,
    stop_sequences=None,
    model: str = settings.LLM_TYPE,
) -> Optional[AsyncGenerator[LLMResponse, None]]:
    response_tokens = 0
    try:
        response = oai_prompt_wrapped(
            prompt,
            temperature,
            max_tokens,
            timeout=timeout,
            inner_timeout=timeout,
            stop_sequences=stop_sequences,
            model=model,
        )
        async for chunk in response:
            response_tokens += 1
            yield LLMResponse(
                text=chunk,
                tokens=response_tokens,
            )
    except (ServiceUnavailableError, APIError, Timeout, APIConnectionError) as e:
        raise GenerationError(beginning_of_exception(str(e)))
    except openai.error.RateLimitError as e:
        raise RateLimitError(beginning_of_exception(str(e)))
    except openai.error.InvalidRequestError as e:
        raise InvalidRequestError(beginning_of_exception(str(e)))
    except ClientPayloadError as e:
        raise GenerationError(beginning_of_exception(str(e)))


async def oai_chat_response(
    prompt: str,
    temperature: float = settings.LLM_TEMPERATURE,
    timeout: int = settings.LLM_TIMEOUT,
    max_tokens: int = settings.LLM_MAX_RESPONSE_TOKENS,
    history=None,
    stop_sequences=None,
    model: str = settings.LLM_TYPE,
) -> Optional[AsyncGenerator[LLMResponse, None]]:
    current_message = {"role": "user", "content": prompt}
    if history is not None:
        history = deepcopy(history)
        history.append(current_message)
    else:
        history = [current_message]

    response_tokens = 0
    try:
        response = oai_chat_wrapped(
            history,
            temperature,
            max_tokens,
            timeout=timeout,
            inner_timeout=timeout,
            stop_sequences=stop_sequences,
            model=model,
        )
        async for chunk in response:
            response_tokens += 1
            yield LLMResponse(
                text=chunk,
                tokens=response_tokens,
            )
    except (ServiceUnavailableError, APIError, Timeout, APIConnectionError) as e:
        raise GenerationError(beginning_of_exception(str(e)))
    except openai.error.RateLimitError as e:
        raise RateLimitError(beginning_of_exception(str(e)))
    except openai.error.InvalidRequestError as e:
        raise InvalidRequestError(beginning_of_exception(str(e)))
    except ClientPayloadError as e:
        raise GenerationError(beginning_of_exception(str(e)))

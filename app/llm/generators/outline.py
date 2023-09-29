import json
import os
import re
import threading
from collections import OrderedDict
from json import JSONDecodeError
from typing import AsyncGenerator, List

from pydantic import BaseModel, parse_obj_as
from tenacity import retry_if_exception_type, stop_after_attempt, retry, wait_fixed

from app.llm.exceptions import GenerationError
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from app.util import extract_only_json_dict

outline_settings = GenerationSettings(
    temperature=0.6,
    max_tokens=1024,
    timeout=60,
    stop_tokens=None,
    prompt_type="outline",
    model=settings.LLM_INSTRUCT_TYPE,
)


class GeneratedOutlineData(BaseModel):
    outline: List[str]
    queries: List[str] | None = None


def outline_prompt(topic: str, concepts: List[str], item_count: int = 10) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, "outline.json")) as f:
        examples = json.load(f)
    input = OrderedDict([("topic", topic), ("concepts", concepts)])
    prompt = build_prompt(
        "outline",
        input,
        examples,
        topic=topic,
        concepts=concepts,
        item_count=item_count,
    )
    return prompt


def parse_json_data(outline: dict) -> GeneratedOutlineData:
    outline = parse_obj_as(GeneratedOutlineData, outline)
    # Get rid of prefix numbers if they exist (they are sometimes added, but we want to strip them out for consistency)
    outline.outline = [
        re.sub(r"^\d+\.\s", "", item).strip() for item in outline.outline
    ]
    return outline


def try_parse_json(text: str) -> dict | None:
    data = None
    try:
        data = json.loads(text.strip())
    except json.decoder.JSONDecodeError:
        # Try to re-parse if it failed
        try:
            data = json.loads(text.strip() + '"]}')
        except json.decoder.JSONDecodeError:
            # If it fails again, keep going with the loop.
            pass
    return data


local_data = threading.local()


def before_retry_callback(retry_state):
    local_data.is_retry = True


def after_retry_callback(retry_state):
    local_data.is_retry = False


@retry(
    retry=retry_if_exception_type(GenerationError),
    stop=stop_after_attempt(2),
    wait=wait_fixed(2),
    before_sleep=before_retry_callback,
    after=after_retry_callback,
    reraise=True,
)
async def generate_outline(
    topic: str,
    concepts: List[str],
    update_after_chars: int = 50,
    item_count: int = 10,
) -> AsyncGenerator[GeneratedOutlineData, None]:
    # Sort concepts alphabetically so that the prompt is the same every time
    concepts = sorted(concepts)
    prompt = outline_prompt(topic, concepts, item_count=item_count)
    text = ""
    # Do not hit cache on retries
    should_cache = not getattr(local_data, "is_retry", False)
    response = generate_response(prompt, outline_settings, cache=should_cache)

    chunk_len = 0
    async for chunk in response:
        text += chunk
        chunk_len += len(chunk)
        if chunk_len >= update_after_chars:
            data = try_parse_json(text.strip())
            if data:
                yield parse_json_data(data)
            chunk_len = 0

    # Handle the last bit of data
    try:
        # Strip out text before/after the json.  Sometimes the LLM will include something before the json input.
        text = extract_only_json_dict(text)
        data = json.loads(text.strip())
    except JSONDecodeError as e:
        raise GenerationError(e)
    yield parse_json_data(data)

import json
import os
import re
import threading
from collections import OrderedDict
from json import JSONDecodeError
from typing import AsyncGenerator, List

import ftfy
from pydantic import BaseModel, parse_obj_as
from tenacity import retry_if_exception_type, stop_after_attempt, retry, wait_fixed

from app.llm.exceptions import GenerationError
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from app.util import extract_only_json_dict

outline_settings = GenerationSettings(
    temperature=0.6,
    max_tokens=1536,
    timeout=1200,
    prompt_type="outline",
    model=settings.LLM_INSTRUCT_TYPE,
)

# This can get better results from a finetuned model, forces a certain outline format
prompt_start_hint = '\n{"outline": ["1. '

class GeneratedOutlineData(BaseModel):
    outline: List[str]
    queries: List[str] | None = None


def outline_prompt(topic: str, potential_outline_items: List[str], item_count: int = settings.SECTIONS_PER_LESSON, include_examples=True) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, "outline.json")) as f:
        examples = json.load(f)

    input = OrderedDict([("topic", topic)])
    has_potential_outline = potential_outline_items and len(potential_outline_items) > 0
    if has_potential_outline:
        input["potential items"] = potential_outline_items
        for example in examples:
            del example["potential items"]

    prompt = build_prompt(
        "outline",
        input,
        examples,
        topic=topic,
        item_count=item_count,
        potential_outline_items=potential_outline_items,
        include_examples=include_examples,
    )
    if settings.FINETUNED:
        prompt += prompt_start_hint
    return prompt


def parse_json_data(outline: dict) -> GeneratedOutlineData:
    outline = parse_obj_as(GeneratedOutlineData, outline)
    # Get rid of prefix numbers if they exist (they are sometimes added, but we want to strip them out for consistency)
    return outline


local_data = threading.local()


def before_retry_callback(retry_state):
    local_data.is_retry = True


def after_retry_callback(retry_state):
    local_data.is_retry = False


@retry(
    retry=retry_if_exception_type(GenerationError),
    stop=stop_after_attempt(5),
    wait=wait_fixed(2),
    before_sleep=before_retry_callback,
    after=after_retry_callback,
    reraise=True,
)
async def generate_outline(
    topic: str,
    potential_outline_items: List[str],
    revision: int,
    item_count: int = 10,
    include_examples: bool = True
) -> GeneratedOutlineData:
    # Sort concepts alphabetically so that the prompt is the same every time
    prompt = outline_prompt(topic, potential_outline_items, item_count=item_count, include_examples=include_examples)
    text = ""
    if settings.FINETUNED:
        text = prompt_start_hint
    # Do not hit cache on retries
    should_cache = not getattr(local_data, "is_retry", False)
    text += await generate_response(prompt, outline_settings, cache=should_cache, revision=revision)

    try:
        # Strip out text before/after the json.  Sometimes the LLM will include something before the json input.
        text = text.replace("\n", " ").strip()
        text = extract_only_json_dict(text)
        text = str(ftfy.fix_text(text))
        data = json.loads(text.strip())
    except JSONDecodeError as e:
        raise GenerationError(e)
    return parse_json_data(data)


def renumber_outline(outline):
    def renumber(match):
        major, minor = int(match.group(1)), match.group(2)
        major -= 1
        return f"{major}{minor}"

    new_outline = [re.sub(r"(\d+)(\..*|$)", renumber, chapter) for chapter in outline]

    return new_outline
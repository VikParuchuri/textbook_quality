import json
import os
from collections import OrderedDict
from json import JSONDecodeError
from typing import List, Optional

from app.llm.exceptions import GenerationError
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from app.util import extract_only_json_list

topic_settings = GenerationSettings(
    temperature=0.9,
    max_tokens=512,
    timeout=40,
    prompt_type="topic",
    model=settings.LLM_INSTRUCT_TYPE,
)


def topic_prompt(book_title: str) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, f"topic.json")) as f:
        examples = json.load(f)
    input = OrderedDict([("title", book_title)])
    prompt = build_prompt("topic", input, examples, title=book_title)
    return prompt


async def generate_topic(
    book_title: str,
) -> List[str]:
    prompt = topic_prompt(book_title)
    text = await generate_response(prompt, topic_settings)
    try:
        text = extract_only_json_list(text)
        data = json.loads(text.strip())
    except JSONDecodeError as e:
        raise GenerationError(e)
    return data


def topic_specific_prompt(book_title: str, domain: Optional[str]) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, f"specific_topic.json")) as f:
        examples = json.load(f)
    input = OrderedDict([("title", book_title)])
    prompt = build_prompt(
        "specific_topic", input, examples, title=book_title, domain=domain
    )
    return prompt


async def generate_specific_topic(
    book_title: str,
    domain: Optional[str] = None,
) -> List[str]:
    prompt = topic_specific_prompt(book_title, domain)
    text = await generate_response(prompt, topic_settings)

    try:
        text = extract_only_json_list(text)
        data = json.loads(text.strip())
    except JSONDecodeError as e:
        raise GenerationError(e)
    return data

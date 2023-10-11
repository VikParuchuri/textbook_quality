import json
import os
from collections import OrderedDict
from copy import deepcopy
from json import JSONDecodeError
from typing import List

import ftfy
from pydantic import BaseModel

from app.llm.exceptions import GenerationError
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from app.util import extract_only_json_dict
from app.llm.adaptors.oai import oai_tokenize_prompt


class GeneratedTOC(BaseModel):
    topic: str
    outline: List[str]
    queries: List[str]


toc_settings = GenerationSettings(
    temperature=0.5,
    max_tokens=1024,
    timeout=1200,
    prompt_type="toc",
    model=settings.LLM_TYPE,
)


def toc_prompt(topic: str, toc: str, include_examples=True) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, "toc.json")) as f:
        examples = json.load(f)
    input = OrderedDict([
        ("topic", topic),
        ("toc", toc),
    ])
    prompt = build_prompt("toc", input, examples, include_examples=include_examples)
    return prompt


async def generate_tocs(topic: str, draft_toc: str, include_examples: bool = True) -> GeneratedTOC | None:
    prompt = toc_prompt(topic, draft_toc, include_examples=include_examples)
    text = ""

    settings_inst = deepcopy(toc_settings)
    try:
        settings_inst.max_tokens = oai_tokenize_prompt(draft_toc) + 512 # Max tokens to generate
    except Exception:
        return

    response = generate_response(prompt, settings_inst)
    async for chunk in response:
        text += chunk
    try:
        text = extract_only_json_dict(text)
        text = str(ftfy.fix_text(text))
        data = json.loads(text.strip())
        toc = data["outline"]
        queries = data["queries"]
    except (JSONDecodeError, IndexError) as e:
        raise GenerationError(e)

    model = GeneratedTOC(topic=topic, outline=toc, queries=queries)
    return model

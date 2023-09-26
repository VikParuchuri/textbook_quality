import json
import os
from collections import OrderedDict
from json import JSONDecodeError
from typing import List

from app.llm.exceptions import GenerationError
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from app.util import extract_only_json_list

title_settings = GenerationSettings(
    temperature=0.9, max_tokens=512, timeout=20, prompt_type="title"
)


def title_prompt(subject: str) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, f"title.json")) as f:
        examples = json.load(f)
    input = OrderedDict([("subject", subject)])
    prompt = build_prompt("title", input, examples)
    return prompt


async def generate_title(
    subject: str,
) -> List[str]:
    prompt = title_prompt(subject)
    text = ""
    response = generate_response(prompt, title_settings, cache=False)
    async for chunk in response:
        text += chunk

    try:
        text = extract_only_json_list(text)
        data = json.loads(text.strip())
    except (JSONDecodeError, IndexError) as e:
        raise GenerationError(e)
    return data

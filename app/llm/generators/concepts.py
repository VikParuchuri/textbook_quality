import json
import os
from collections import OrderedDict
from json import JSONDecodeError
from typing import List

from pydantic import BaseModel

from app.llm.exceptions import GenerationError
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from app.util import extract_only_json_dict


class CourseGeneratedConcepts(BaseModel):
    topic: str
    concepts: List[str]
    feasible: bool


concept_settings = GenerationSettings(
    temperature=0.7,
    max_tokens=256,
    timeout=20,
    stop_tokens=None,
    prompt_type="concept",
    model=settings.LLM_INSTRUCT_TYPE,
)


def concept_prompt(topic: str) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, "concepts.json")) as f:
        examples = json.load(f)
    input = OrderedDict([("topic", topic)])
    prompt = build_prompt("concepts", input, examples)
    return prompt


async def generate_concepts(topic: str) -> CourseGeneratedConcepts:
    prompt = concept_prompt(topic)
    text = ""
    response = generate_response(prompt, concept_settings)
    async for chunk in response:
        text += chunk
    try:
        text = extract_only_json_dict(text)
        data = json.loads(text.strip())
        concepts = data["concepts"]
        feasible = data["feasible"]
    except (JSONDecodeError, IndexError) as e:
        raise GenerationError(e)

    model = CourseGeneratedConcepts(topic=topic, concepts=concepts, feasible=feasible)
    return model

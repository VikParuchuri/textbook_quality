import json
import os
from collections import OrderedDict
from json import JSONDecodeError
from typing import List

from pydantic import BaseModel
from tenacity import stop_after_attempt, wait_fixed, before, after, retry, retry_if_exception_type
import threading

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
    timeout=40,
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


local_data = threading.local()


def before_retry_callback(retry_state):
    local_data.is_retry = True


def after_retry_callback(retry_state):
    local_data.is_retry = False


@retry(
    retry=retry_if_exception_type(GenerationError),
    stop=stop_after_attempt(2),
    wait=wait_fixed(2),
    before=before_retry_callback,
    after=after_retry_callback,
    reraise=True,
)
async def generate_concepts(topic: str) -> CourseGeneratedConcepts:
    prompt = concept_prompt(topic)
    text = ""
    # If we should cache the prompt - skip cache if we're retrying
    should_cache = not getattr(local_data, "is_retry", False)
    response = generate_response(prompt, concept_settings, cache=should_cache)
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

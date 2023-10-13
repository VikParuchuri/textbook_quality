import json
import os
from collections import OrderedDict
from typing import AsyncGenerator, List, get_args

from app.course.schemas import ResearchNote
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt, render_research_notes
from app.settings import settings

rewrite_settings = GenerationSettings(
    temperature=.6,
    max_tokens=6000,
    timeout=1200,
    prompt_type="rewrite"
)


def rewrite_prompt(
    topic: str,
    draft: str,
    include_examples: bool,
    research_notes: List[ResearchNote] | None = None,
) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, "rewrite.json")) as f:
        examples = json.load(f)

    items = [("topic", topic)]

    research_notes_exist = research_notes is not None and len(research_notes) > 0
    if research_notes_exist:
        research_content = render_research_notes(research_notes)
        items.append(("research notes\n", research_content))

    items.append(("draft\n", draft))

    input = OrderedDict(items)

    prompt = build_prompt(
        "rewrite",
        input,
        examples,
        include_examples=include_examples,
        topic=topic,
        research_notes=research_notes_exist,
    )
    return prompt


async def generate_rewrite(
    topic: str,
    draft: str,
    revision: int,
    research_notes: List[ResearchNote] | None = None,
    include_examples: bool = True,
    cache: bool = True,
) -> str:
    prompt = rewrite_prompt(
        topic,
        draft,
        include_examples,
        research_notes,
    )

    text = await generate_response(prompt, rewrite_settings, cache=cache, revision=revision)

    return text

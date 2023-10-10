import json
import os
from collections import OrderedDict
from typing import AsyncGenerator, List, get_args

from app.components.schemas import ComponentNames
from app.course.schemas import ResearchNote
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt
from app.settings import settings
from copy import deepcopy

lesson_settings = GenerationSettings(
    temperature=0.4,
    max_tokens=6000,
    timeout=1200,
    prompt_type="lesson",
)

COMPONENT_EXTRAS = {
    "exercise": "* ---exercise specifies an exercise. Exercises enable learners to practice the skills learned in the text. They should be challenging and require understanding the text fully (no multiple choice). Exercises should contain instructions and the correct answer. Include 1 exercise block per section.",
    "text": "* ---text specifies a text block. Text blocks are the main content of the course, and teach the learner relevant concepts. Text should be in Github-flavored markdown. Inline math equations should be surrounded with $ symbols, and block math should be surrounded with $$. Include several text blocks per section.",
    "section": "* ---section specifies a section header. Each section matches an item in the outline.",
    "example": "* ---example specifies an example. Examples are used to illustrate concepts found in the text in a practical way.",
}


def lesson_prompt(
    outline: List[str],
    current_section: str,
    current_section_index: int,
    topic: str,
    components: List[str],
    include_examples: bool,
    research_notes: List[ResearchNote] | None = None,
) -> str:
    with open(os.path.join(settings.EXAMPLE_JSON_DIR, "lesson.json")) as f:
        examples = json.load(f)

    # Set default components if none are provided
    if not components:
        components = list(get_args(settings.VALID_GENERATED_COMPONENTS))

    # Strip out components that can't be generated from input
    components = [
        c
        for c in components
        if c in list(get_args(settings.VALID_GENERATED_COMPONENTS))
    ]

    # Basic components that are needed in every lesson
    components += [ComponentNames.text.value, ComponentNames.section.value]
    components = sorted(list(set(components)))

    for example in examples:
        blocks = example["markdown"]
        markdown = ""
        for block_type, content in blocks:
            if block_type in components:
                markdown += f"---{block_type}\n{content}"
        example["markdown"] = markdown

    # Generate a list of extra sentences to be added in to the prompt that are component specific.
    component_extras = [COMPONENT_EXTRAS.get(c, None) for c in components]
    component_extras = [c for c in component_extras if c is not None]

    sections_to_author = len(outline) - current_section_index
    outline_items_to_author = outline[
        current_section_index: current_section_index + sections_to_author
    ]
    outline_items_to_author_str = ",".join(outline_items_to_author)
    outline_stop_item = outline_items_to_author[-1]

    selected_outline = deepcopy(outline)
    if len(outline) > settings.SECTIONS_PER_LESSON:
        surround = min(settings.SECTIONS_PER_LESSON // 2, 10)
        start_item = max(current_section_index - surround, 0)
        end_item = min(current_section_index + sections_to_author + surround, len(outline))
        selected_outline = selected_outline[start_item:end_item]

    rendered_outline = "\n".join(selected_outline).strip()
    items = [
        ("Table of contents\n", rendered_outline),
    ]

    research_notes_exist = research_notes is not None and len(research_notes) > 0
    if research_notes_exist:
        research_content = ""
        for research_note in research_notes:
            content = research_note.content.replace("```", " ")
            content = f"```{content}```"
            research_content += f"* {content}\n"
        items.append(("research notes\n", research_content))

    items.append(("course\n\n", current_section))

    input = OrderedDict(items)

    section_str = "section" if sections_to_author == 1 else "sections"

    prompt = build_prompt(
        "lesson",
        input,
        examples,
        include_examples=include_examples,
        topic=topic,
        components=components,
        component_extras=component_extras,
        research_notes=research_notes_exist,
        section_count=len(outline),
        sections_to_author=sections_to_author,
        section_str=section_str,
        outline_items_to_author=outline_items_to_author_str,
        outline_stop_item=outline_stop_item,
    )
    return prompt


async def generate_lessons(
    outline: List[str],
    current_section: str,
    current_section_index: int,
    topic: str,
    components: List[str],
    revision: int,
    research_notes: List[ResearchNote] | None = None,
    include_examples: bool = True,
    update_after_chars: int = 500,
    cache: bool = True,
    stop_section: str | None = None,
) -> AsyncGenerator[str, None]:
    prompt = lesson_prompt(
        outline,
        current_section,
        current_section_index,
        topic,
        components,
        include_examples,
        research_notes,
    )

    text = ""
    stop_sequences = None
    if stop_section is not None:
        stop_sequences = [stop_section]

    response = generate_response(prompt, lesson_settings, cache=cache, revision=revision, stop_sequences=stop_sequences)
    chunk_len = 0

    # Yield text in batches, to avoid creating too many DB models
    async for chunk in response:
        text += chunk
        chunk_len += len(chunk)
        if chunk_len >= update_after_chars:
            yield text
            chunk_len = 0
    # Yield the remaining text
    yield text

import json
import os
import re
from collections import OrderedDict, Counter, defaultdict
from typing import AsyncGenerator, List, get_args, Optional

from app.course.schemas import ResearchNote
from app.llm.llm import GenerationSettings, generate_response
from app.llm.prompts import build_prompt, render_research_notes
from app.settings import settings

rewrite_settings = GenerationSettings(
    temperature=.6,
    max_tokens=4000,
    timeout=1200,
    prompt_type="rewrite"
)


def rewrite_prompt(
    topic: str,
    draft: str,
    include_examples: bool,
    markdown: Optional[str] = None,
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

    if markdown:
        items.append(("markdown\n", markdown))

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
    markdown: str | None = None, # The previous section markdown
    research_notes: List[ResearchNote] | None = None,
    include_examples: bool = True,
    cache: bool = True,
) -> str:
    prompt = rewrite_prompt(
        topic,
        draft,
        include_examples,
        markdown,
        research_notes,
    )

    text = await generate_response(prompt, rewrite_settings, cache=cache, revision=revision)
    return text


def title_case(s):
    return re.sub(r'\w+', lambda m: m.group(0).lower().capitalize(), s)

def ending_punctuation(s):
    return bool(re.search(r'[!?.,;:\'"-]$', s))

def extract_titles(text: str) -> (List[str], List[int]):
    lines = text.split("\n")

    # Find all potential titles
    potential_titles = []
    for i, line in enumerate(lines[2:]):
        line = line.strip()
        if not line or line[0].isupper():
            prev = lines[i - 1]
            if len(prev) > 10 and prev[0].isupper() and not ending_punctuation(prev):
                if len(lines[i - 2].strip()) < 20 or ending_punctuation(lines[i - 2]):
                    potential_titles.append((prev, i - 1))

    # Count the number of times each potential title appears, and find first appearance
    min_position = {}
    counter = defaultdict(int)
    for potential_title in potential_titles:
        counter[potential_title[0]] += 1
        if potential_title not in min_position:
            min_position[potential_title[0]] = potential_title[1]

    # Extract the most seen potential titles
    total_titles = min(20, max(10, len(lines) // 500))
    titles = sorted([(k, v) for k, v in counter.items() if v > 1], key=lambda x: x[1], reverse=True)[:total_titles]
    positions = [min_position[t[0]] for t in titles]
    titles = [title_case(t[0]).strip() for t in titles]

    # Sort in ascending order of position
    sorted_titles = sorted(zip(positions, titles))
    positions, titles = zip(*sorted_titles)

    return list(titles), list(positions)

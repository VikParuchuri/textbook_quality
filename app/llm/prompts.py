import json
from collections import OrderedDict
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, Template

from app.settings import settings


def render_single_dict(d: OrderedDict) -> str:
    prompt = ""
    for k in d.keys():
        if k in ["json", "markdown"]:
            continue
        header = k.replace("_", " ").title()
        if not header.endswith((":", "?", ".", "#", "\n")):
            header += ":"
        if not header.endswith(("\n", " ")):
            header += " "
        prompt += f"{header}{str(d[k])}\n"
    if "json" in d:
        prompt += json.dumps(d["json"])
    if "markdown" in d:
        prompt += f"\n{d['markdown']}"
    return prompt


def render_examples(examples: List[OrderedDict]) -> str:
    if examples is None:
        return ""
    example_prompt = ""
    for i, example in enumerate(examples):
        example_prompt += f"Example {i + 1}\n"
        example_prompt += render_single_dict(example)
        example_prompt += "\n"
    return example_prompt


def render_input(input: OrderedDict) -> str:
    if input is None:
        return ""
    input_prompt = "Input\n"
    input_prompt += render_single_dict(input)
    return input_prompt


def build_prompt(
    template_name: str,
    input: OrderedDict,
    examples: Optional[list] = None,
    include_examples: bool = True,
    **keys,
) -> str:
    with open(f"{settings.PROMPT_TEMPLATE_DIR}/{template_name}.jinja") as file_:
        template_str = file_.read()
    template = Environment(
        loader=FileSystemLoader(settings.PROMPT_TEMPLATE_DIR)
    ).from_string(template_str)
    instruction = template.render(**keys)
    input_prompt = render_input(input)
    if include_examples:
        example_prompt = render_examples(examples)
        prompt = f"{instruction}\n\n{example_prompt}\n{input_prompt}"
    else:
        prompt = f"{instruction}\n\n{input_prompt}"
    return prompt

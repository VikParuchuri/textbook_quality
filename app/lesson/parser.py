import re
from typing import List, get_args

from app.components.parser import parse_single_component
from app.components.schemas import COMPONENT_MAP, AllLessonComponentData, ComponentNames
from app.settings import settings


def parse_lesson_markdown(markdown: str) -> List[AllLessonComponentData]:
    # We need to add a section header into the markdown that is generated
    components = []

    lines = markdown.split("\n")
    current_markdown = ""
    current_type = None

    for line in lines:
        if line.startswith("---"):
            if len(current_markdown) > 0 and current_type:
                components.append((current_type, current_markdown.strip()))

            current_type = re.sub("-+", "", line).strip()
            current_markdown = ""
        else:
            current_markdown += line + "\n"
    # Add in the last component
    if len(current_markdown) > 0 and current_type:
        components.append((current_type, current_markdown.strip()))
    return parse_component_list(components)


def parse_component_list(
    components: List[tuple[str, str]]
) -> List[AllLessonComponentData]:
    new_components = []
    for type, markdown in components:
        # Ignore any components that we don't expect
        if type not in list(get_args(settings.VALID_GENERATED_COMPONENTS)):
            continue
        new_components.append(parse_single_component(type, markdown))
    return new_components


def render_lesson_to_markdown(
    components: List[tuple[str, str]], include_type=True
) -> str:
    markdown = ""
    for type, content in components:
        if include_type:
            markdown += f"\n\n---{type}\n\n{content.strip()}"
        else:
            markdown += f"\n\n{content.strip()}"
    return markdown


def render_components_to_markdown(components: List[AllLessonComponentData]) -> str:
    tuples: List[tuple[str, str]] = []
    for component in components:
        match component.type:
            case ComponentNames.exercise:
                tuples.append(
                    (
                        component.type,
                        f"Instructions:\n\n{component.instructions}\n\nSolution:\n\n{component.solution}",
                    )
                )
            case _:
                tuples.append((component.type, component.markdown))
    return render_lesson_to_markdown(tuples, include_type=True)

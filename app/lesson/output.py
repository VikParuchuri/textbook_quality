import re
from typing import List

from app.components.schemas import AllLessonComponentData, ComponentNames
from app.lesson.parser import render_lesson_to_markdown


def render_components_to_output_markdown(
    components: List[AllLessonComponentData],
) -> str:
    tuples: List[tuple[str, str]] = []
    for component in components:
        match component.type:
            case ComponentNames.exercise:
                solution = component.solution.strip() if component.solution else ""
                exercise = f"## Exercise\n{component.instructions.strip()}"
                if len(solution) > 0:
                    exercise += f"\n\n### Solution\n{solution}"

                tuples.append(
                    (
                        component.type,
                        exercise,
                    )
                )
            case ComponentNames.section:
                component.markdown = remove_leading_number_and_period(
                    component.markdown
                )
                if not component.markdown.startswith("#"):
                    component.markdown = f"# {component.markdown}"
                tuples.append((component.type, component.markdown))
            case ComponentNames.text:
                tuples.append(
                    (component.type, remove_section_paragraphs(component.markdown))
                )
            case _:
                tuples.append((component.type, component.markdown))
    return render_lesson_to_markdown(tuples, include_type=False)


def remove_section_paragraphs(text):
    # Split text into paragraphs
    paragraphs = text.split("\n")

    # Check if the first paragraph contains "in this section" and remove it if true
    if "in this section" in paragraphs[0].lower():
        paragraphs.pop(0)

    if len(paragraphs) > 0:
        # Check if the last paragraph contains "in the next section" and remove it if true
        if "in the next section" in paragraphs[-1].lower():
            paragraphs.pop()

    # Reconstruct the text from the remaining paragraphs
    return "\n".join(paragraphs).strip()


def remove_leading_number_and_period(s):
    # Use regex to match an optional "# " followed by a number, period, and a space
    return re.sub(r"^(#\s)?\d+\.\s*", "", s)

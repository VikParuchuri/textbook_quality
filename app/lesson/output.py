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
                markdown_data = component.markdown.strip()
                if not markdown_data.startswith("#"):
                    markdown_data = f"# {markdown_data}"
                tuples.append((component.type, markdown_data))
            case ComponentNames.text:
                markdown_data = component.markdown.strip()
                tuples.append(
                    (component.type, remove_section_paragraphs(markdown_data))
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
    replaced = "\n".join(paragraphs).strip()
    replaced = re.sub(r"\n\n+", "\n\n", replaced)
    return replaced

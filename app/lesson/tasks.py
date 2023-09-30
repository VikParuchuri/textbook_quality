from copy import deepcopy
from typing import AsyncGenerator, List

from app.components.parser import generate_component_key
from app.components.schemas import (
    COMPONENT_VERSION,
    AllLessonComponentData,
    ComponentNames,
    MarkdownComponentData,
)
from app.lesson.parser import parse_lesson_markdown, render_components_to_markdown
from app.course.schemas import ResearchNote
from app.llm.exceptions import GenerationError, InvalidRequestError, RateLimitError
from app.llm.generators.lesson import generate_lessons
from app.settings import settings
from app.util import debug_print_trace


async def generate_lesson(
    course_name: str,
    course_components: List[str],
    outline: List[str],
    research_notes: List[ResearchNote] | None = None,
) -> List[AllLessonComponentData] | None:
    # Add numbers to the outline - needed for generating the lesson
    numbered_outline = [f"{i + 1}. {outline}" for i, outline in enumerate(outline)]

    components = []
    generated_sections = 0
    iterations = generated_sections

    while generated_sections < len(numbered_outline) and iterations < len(
        numbered_outline
    ):
        # This is to prime the model with data on what has already been generated
        # The first pass will just include the first section header
        # Subsequent passes will include the previous section and the current section header
        last_section = ""
        if len(components) > 0:
            last_header_index = [
                i for i, c in enumerate(components) if c.type == ComponentNames.section
            ][-1]
            last_section_components = components[last_header_index:]

            # Filter out diagrams, since they take up a lot of tokens.
            # The instructional content should be in the text and examples.
            last_section = render_components_to_markdown(last_section_components)

        current_section_component = MarkdownComponentData(
            type=ComponentNames.section,
            markdown=numbered_outline[generated_sections],
            key=generate_component_key(),
            version=COMPONENT_VERSION,
        )
        components.append(current_section_component)
        current_section_header = render_components_to_markdown(
            [current_section_component]
        )

        current_section = f"{last_section}\n\n{current_section_header}".strip()

        # Filter research notes to save tokens, only keep notes relevant to the next 5 sections
        # Find the indices of the next sections
        future_sections = set(list(range(generated_sections, len(numbered_outline)))[:5])
        selected_research_notes = None
        if research_notes is not None:
            selected_research_notes = []
            for research_note in research_notes:
                # If the research note is needed in the next sections
                if set(research_note.outline_items) & future_sections:
                    selected_research_notes.append(research_note)

        try:
            response = generate_single_lesson_chunk(
                numbered_outline,
                current_section,
                generated_sections,
                course_name,
                course_components,
                research_notes=selected_research_notes,
                include_examples=settings.INCLUDE_EXAMPLES,
            )
            new_components = []
            new_component_keys = []
            async for chunk in response:
                new_components = chunk
                # Set keys for the new components to the same as the ones in the last iteration
                for i, key in enumerate(new_component_keys):
                    new_components[i].key = key
                new_component_keys = [c.key for c in new_components]
        except (GenerationError, RateLimitError, InvalidRequestError) as e:
            debug_print_trace()
            print(f"Error generating lesson: {e}")
            return
        except Exception as e:
            debug_print_trace()
            print(f"Error generating lesson: {e}")
            return

        components = deepcopy(components + new_components)

        iterations += 1
        generated_sections = len(
            [c for c in components if c.type == ComponentNames.section]
        )
    return components


async def generate_single_lesson_chunk(
    numbered_outline: List[str],
    current_section: str,
    current_section_index: int,
    course_name: str,
    components: List[str],
    research_notes: List[ResearchNote] | None,
    include_examples: bool,
) -> AsyncGenerator[List[AllLessonComponentData], None]:
    response = generate_lessons(
        numbered_outline,
        current_section,
        current_section_index,
        course_name,
        components,
        research_notes=research_notes,
        include_examples=include_examples,
    )

    async for chunk in response:
        new_components = parse_lesson_markdown(chunk)
        yield new_components

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
    revision: int,
    research_notes: List[ResearchNote] | None = None,
    sections_per_generation: int = settings.SECTIONS_PER_GENERATION,
) -> List[AllLessonComponentData] | None:
    # Add numbers to the outline - needed for generating the lesson
    numbered_outline = outline

    components = []
    generated_sections = 0
    iterations = 0
    use_cache = True

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

        current_section = f"{last_section.strip()}\n\n{current_section_header.strip()}"
        current_section = f"{current_section}\n"

        # When to stop generation
        stop_section = None
        if generated_sections + sections_per_generation < len(numbered_outline):
            stop_section = numbered_outline[generated_sections + sections_per_generation]

        # Filter research notes to save tokens, only keep notes relevant to the next 5 sections
        # Find the indices of the next sections
        future_sections = set(list(range(generated_sections, len(numbered_outline)))[:sections_per_generation])
        selected_research_notes = None
        if research_notes is not None:
            selected_research_notes = []
            for research_note in research_notes:
                # If the research note is needed in the next sections
                if set(research_note.outline_items) & future_sections:
                    selected_research_notes.append(research_note)

        try:
            new_components = await generate_single_lesson_chunk(
                numbered_outline,
                current_section,
                generated_sections,
                course_name,
                course_components,
                revision,
                research_notes=selected_research_notes,
                include_examples=settings.INCLUDE_EXAMPLES,
                cache=use_cache,
                stop_section=stop_section,
            )
        except (GenerationError, RateLimitError, InvalidRequestError) as e:
            debug_print_trace()
            print(f"Error generating lesson: {e}")
            return
        except Exception as e:
            debug_print_trace()
            print(f"Error generating lesson: {e}")
            return

        components = deepcopy(components + new_components)

        all_section_headers = [
                i for i, c in enumerate(components) if c.type == ComponentNames.section
            ]
        last_section_index = all_section_headers[-1]

        # Handle partially generated (cut-off) sections
        # Only do this if there are few components, and it's not the end of the lesson
        if len(components) - last_section_index <= 2 and \
                len(components[-1].markdown) < 500 and \
                len(all_section_headers) < len(numbered_outline):
            # If we don't have enough components in the last section, it may have been cut off
            components = components[:last_section_index]
            use_cache = False
        else:
            use_cache = True

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
    revision: int,
    research_notes: List[ResearchNote] | None,
    include_examples: bool,
    cache: bool,
    stop_section: str | None = None,
) -> List[AllLessonComponentData]:
    chunk = await generate_lessons(
        numbered_outline,
        current_section,
        current_section_index,
        course_name,
        components,
        revision,
        research_notes=research_notes,
        include_examples=include_examples,
        cache=cache,
        stop_section=stop_section,
    )

    section_start = f"---{ComponentNames.section}"

    # Remove the final section header from the chunk
    # This happens when we hit the stop token
    chunk = chunk.strip()
    # Remove the section header from the chunk
    if chunk.endswith(section_start):
        chunk = chunk[:-len(section_start)]

    if stop_section and chunk.endswith(stop_section):
        chunk = chunk[:-len(stop_section)]

    chunk = chunk.strip()

    new_components = parse_lesson_markdown(chunk)
    if len(new_components) > 1 and new_components[-1].type == ComponentNames.section:
        # Remove the final section header from the chunk
        new_components = new_components[:-1]

    return new_components

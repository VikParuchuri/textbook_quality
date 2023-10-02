from typing import List

from app.course.embeddings import EmbeddingContext
from app.course.schemas import ResearchNote
from app.llm.exceptions import GenerationError, InvalidRequestError, RateLimitError
from app.llm.generators.concepts import generate_concepts
from app.llm.generators.outline import generate_outline
from app.services.generators.pdf import download_and_parse_pdfs, search_pdfs
from app.util import debug_print_trace


async def create_course_concepts(course_name: str):
    """
    Set the topic and concepts for a course async.
    """
    topic = None
    generated_concepts = None
    try:
        concepts = await generate_concepts(course_name)
        if concepts.feasible:
            generated_concepts = concepts.concepts
    except (GenerationError, RateLimitError, InvalidRequestError) as e:
        debug_print_trace()
        print(f"Error generating concepts for {course_name}: {e}")

    return generated_concepts


async def create_course_outline(
    course_name: str, concepts: List[str], outline_items: int
):
    outline_list = None
    queries = None
    try:
        response = generate_outline(course_name, concepts, item_count=outline_items)

        # Stream outline as it generates
        async for outline_data in response:
            outline_list = outline_data.outline
            queries = outline_data.queries
    except (GenerationError, RateLimitError, InvalidRequestError) as e:
        debug_print_trace()
        print(f"Error generating outline for {course_name}")

    return outline_list, queries


async def query_course_context(
    model, queries: List[str], outline_items: List[str]
) -> List[ResearchNote] | None:
    # Store the pdf data in the database
    pdf_results = await search_pdfs(queries)
    pdf_data = await download_and_parse_pdfs(pdf_results)

    # If there are no resources, don't generate research notes
    if len(pdf_data) == 0:
        return

    embedding_context = EmbeddingContext(model)
    embedding_context.add_resources(pdf_data)

    results = embedding_context.query(outline_items)
    return results

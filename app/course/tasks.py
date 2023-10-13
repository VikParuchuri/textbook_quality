from typing import List

from tenacity import RetryError

from app.course.embeddings import EmbeddingContext
from app.course.schemas import ResearchNote
from app.llm.exceptions import GenerationError, InvalidRequestError, RateLimitError
from app.llm.generators.concepts import generate_concepts
from app.llm.generators.outline import generate_outline
from app.services.generators.pdf import download_and_parse_pdfs, search_pdfs
from app.services.generators.wiki import search_wiki
from app.settings import settings
from app.util import debug_print_trace


async def create_course_concepts(course_name: str, revision: int):
    """
    Set the topic and concepts for a course async.
    """
    generated_concepts = None
    try:
        concepts = await generate_concepts(course_name, revision, include_examples=settings.INCLUDE_EXAMPLES)
        if concepts.feasible:
            generated_concepts = concepts.concepts
    except (GenerationError, RateLimitError, InvalidRequestError, RetryError) as e:
        debug_print_trace()
        print(f"Error generating concepts for {course_name}: {e}")

    return generated_concepts


async def create_course_outline(
    course_name: str, concepts: List[str], outline_items: int, revision: int
):
    outline_list = None
    queries = None
    try:
        outline_data = await generate_outline(course_name, concepts, revision, item_count=outline_items, include_examples=settings.INCLUDE_EXAMPLES)
        outline_list = outline_data.outline
        queries = outline_data.queries
    except (GenerationError, RateLimitError, InvalidRequestError, RetryError) as e:
        debug_print_trace()
        print(f"Error generating outline for {course_name}")

    return outline_list, queries


async def query_course_context(
    model, queries: List[str], outline_items: List[str], course_name: str
) -> List[ResearchNote] | None:
    # Store the pdf data in the database
    # These are general background queries
    pdf_results = await search_pdfs(queries)
    pdf_data = await download_and_parse_pdfs(pdf_results)

    # Make queries for each chapter and subsection, but not below that level
    # These are specific queries related closely to the content
    specific_queries = [f"{course_name}: {o}" for o in outline_items if o.count(".") < 3]
    if settings.CUSTOM_SEARCH_SERVER:
        if "wiki" in settings.CUSTOM_SEARCH_TYPES:
            wiki_results = await search_wiki(specific_queries)
            pdf_data += wiki_results

    # If there are no resources, don't generate research notes
    if len(pdf_data) == 0:
        return

    embedding_context = EmbeddingContext(model)
    embedding_context.add_resources(pdf_data)

    results = embedding_context.query(outline_items)

    return results

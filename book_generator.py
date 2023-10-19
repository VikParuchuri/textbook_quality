import math
from typing import Optional, Dict, List
import argparse
import asyncio

from pyarrow._json import ReadOptions
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from app.db.session import get_session
from app.db.tables import * # Needed to avoid errors with table imports
from app.course.tasks import create_course_concepts, create_course_outline, query_course_context
from app.course.models import load_cached_course, Course
from app.lesson.tasks import generate_lesson
from app.lesson.output import render_components_to_output_markdown
from app.llm.generators.outline import renumber_outline
from app.llm.generators.rewrite import extract_titles_only
from app.settings import settings
import json
import os
import random
import ray

from app.util import debug_print_trace, exact_deduplicate


async def save_course(course: Course):
    async with get_session() as db:
        db.add(course)
        await db.commit()


def get_json_data_from_course(course: Course, extended_fields=False):
    json_data = {
        "topic": course.topic,
        "model": settings.LLM_TYPE,
        "concepts": course.concepts,
        "outline": course.outline,
        "markdown": course.markdown,
    }

    if extended_fields:
        if isinstance(course.components[0], str):
            json_data["components"] = course.components
        else:
            json_data["components"] = [c.json() for c in course.components]

        if course.context is None or len(course.context) == 0 or isinstance(course.context[0], str):
            json_data["context"] = course.context
        else:
            json_data["context"] = [v.json() for v in course.context]
        json_data["queries"] = course.queries
        json_data["potential_outline"] = course.potential_outline_items
    return json.dumps(json_data)


async def generate_single_course(model, course_data: Dict | str, revision=1, outline_items=settings.TOTAL_OUTLINE_ITEMS, cache_only=False):
    components = ["exercise", "example"]

    outline = None
    queries = None
    documents = None
    concepts = []
    potential_outline_items = []
    if isinstance(course_data, dict):
        course_name = course_data["topic"]
        outline = course_data.get("outline")
        queries = course_data.get("queries")
        documents = course_data.get("documents") # Optional field for custom embedding document
    else:
        course_name = course_data

    course = await load_cached_course(settings.LLM_TYPE, course_name, revision)
    if course is not None:
        await asyncio.sleep(0.01) # small sleep to avoid excess db load
        return course

    if cache_only:
        return None

    if not outline:
        if documents:
            for doc in documents:
                try:
                    titles = extract_titles_only(doc)
                    potential_outline_items.extend(titles)
                except ValueError:
                    # This happens when titles can't be extracted from the doc
                    pass

        outline, queries = await create_course_outline(course_name, potential_outline_items, outline_items, revision)

        if outline is None:
            return

        # Remove the intro if it exists
        if "intro" in outline[0].lower():
            outline = outline[1:]
            # Remove sections of intro
            while outline[0].startswith("1."):
                outline = outline[1:]
            outline = renumber_outline(outline)

    context = None
    if queries is not None:
        try:
            # Up to one retrieved passage per outline item
            # Remove numbers from outline for use in retrieval
            context_outline = [item.split(" ", 1)[-1] for item in outline]
            context = await query_course_context(model, queries, context_outline, course_name, documents=documents)
        except Exception as e:
            debug_print_trace()
            print(f"Error generating context for {course_name}: {e}")

    components = await generate_lesson(course_name, components, outline, revision, research_notes=context)
    if components is None:
        return

    md = render_components_to_output_markdown(components)

    course = Course(
        topic=course_name,
        model=settings.LLM_TYPE,
        outline=outline,
        potential_outline_items=potential_outline_items,
        concepts=concepts,
        markdown=md,
        components=components,
        context=context,
        queries=queries if queries is not None else [],
        version=revision
    )
    await save_course(course)

    return course


async def _process_course(model, topic, args):
    try:
        return await generate_single_course(model, topic, revision=args.revision, cache_only=args.cache_only)
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating course: {e}")


async def _process_courses(model, courses, args):
    processes = [_process_course(model, course, args) for course in courses]
    return await asyncio.gather(*processes)


@ray.remote(num_cpus=settings.RAY_CORES_PER_WORKER)
def process_course(model, course, args):
    try:
        return asyncio.run(_process_course(model, course, args))
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating course: {e}")


def load_json_topics(in_files: List[str], max: int | None = None):
    loaded_topics = []
    for in_file in in_files:
        with open(in_file) as f:
            topics = json.load(f)

        if max:
            topics = topics[:max]

        random.seed(1)
        random.shuffle(topics)
        loaded_topics += topics

    loaded_topics = exact_deduplicate(loaded_topics) # Deduplicate topic names
    return loaded_topics


def load_data_in_blocks(data_files: List[str], block_size: int, max_courses: int | None = None):
    data_files = [os.path.join(settings.DATA_DIR, f) for f in data_files]
    is_jsonl = data_files[0].endswith("jsonl")
    if is_jsonl and len(data_files) > 1:
        raise Exception("Can't load multiple jsonl files")

    if is_jsonl:
        with open(data_files[0]) as f:
            block = []  # Initialize the block
            lines_processed = 0
            for line in f:  # Read the file line by line
                try:
                    block.append(json.loads(line.rstrip()))
                    lines_processed += 1
                except Exception:
                    print(f"Malformed json line in file")

                if max_courses and lines_processed >= max_courses:
                    yield block
                    break

                if len(block) >= block_size:
                    yield block
                    block = []
    else:
        loaded_data = load_json_topics(data_files, max_courses)
        for i in range(0, len(loaded_data), block_size):
            yield loaded_data[i:i + block_size]


def process_single_chunk(model_ref, topics, args):
    futures = [process_course.remote(model_ref, course, args) for course in topics]

    # Run all ray tasks
    courses = []
    progress_bar = tqdm(total=len(futures))
    while len(futures) > 0:
        finished, futures = ray.wait(
            futures, timeout=7.0
        )
        course = ray.get(finished)
        courses.extend(course)
        progress_bar.update(len(course))
    return courses


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Given a topic file, generate synthetic books.")
    parser.add_argument("in_file", help="Input filename (flat json list of topics, or jsonl file with dictionaries with keys topic, queries, and outline).  One file or a comma-separated list of files.")
    parser.add_argument("out_file", help="Output filename (jsonl)")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of courses to generate")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers to use")
    parser.add_argument("--extended-fields", action="store_true", default=False, help="Include extended fields in output")
    parser.add_argument("--revision", type=int, default=1, help="Revision number for the course.  Change this to avoid hitting cache if you want to regenerate a course.")
    parser.add_argument("--cache-only", action="store_true", default=False, help="Only use the cache, don't generate any new courses")

    args = parser.parse_args()

    # Load in topics, limit to max if needed
    # Also shuffle randomly (with a seed)
    in_files = args.in_file.split(",")
    max_courses = None
    if args.max:
        max_courses = args.max // len(in_files)

    total_processes = math.ceil(args.workers * settings.RAY_CORES_PER_WORKER)

    ray.init(
        num_cpus=total_processes,
        storage=settings.RAY_CACHE_PATH,
        _temp_dir=settings.RAY_CACHE_PATH,
        dashboard_host=settings.RAY_DASHBOARD_HOST
    )

    model = SentenceTransformer("TaylorAI/gte-tiny")
    model_ref = ray.put(model)

    courses = []
    print(f"Generating course batches with {total_processes} processes from filename(s) {in_files}")
    for topics in load_data_in_blocks(in_files, settings.PROCESS_CHUNK_SIZE, max_courses=max_courses):
        # Run ray tasks on split chunk
        courses.extend(process_single_chunk(model_ref, topics, args))

    course_count = 0
    with open(os.path.join(settings.DATA_DIR, args.out_file), "w+") as f:
        for course in courses:
            # Filter out courses that didn't generate properly
            if course is None or isinstance(course, Exception):
                continue

            if course.markdown is None or len(course.markdown) == 0:
                continue

            course_count += 1
            json_data = get_json_data_from_course(course, extended_fields=args.extended_fields)
            f.write(json_data + '\n')
    print(f"Generated {course_count} courses")
    ray.shutdown()




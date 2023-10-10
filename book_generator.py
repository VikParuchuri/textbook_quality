import asyncio
import math
from typing import Optional, Dict
import argparse

from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from app.db.session import get_session
from app.db.tables import * # Needed to avoid errors with table imports
from app.course.tasks import create_course_concepts, create_course_outline, query_course_context
from app.course.models import load_cached_course, Course
from app.lesson.tasks import generate_lesson
from app.lesson.output import render_components_to_output_markdown
from app.llm.generators.outline import renumber_outline
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
    return json.dumps(json_data)


async def generate_single_course(model, course_data: Dict | str, revision=1, outline_items=12, cache_only=False):
    components = ["exercise", "example"]

    outline = None
    queries = None
    concepts = []
    if isinstance(course_data, dict):
        course_name = course_data["topic"]
        outline = course_data["outline"]
        queries = course_data["queries"]
    else:
        course_name = course_data

    course = await load_cached_course(settings.LLM_TYPE, course_name, revision)
    if course is not None:
        await asyncio.sleep(.001) # Sleep to avoid high CPU usage with many workers
        return course

    if cache_only:
        return None

    if not outline:
        # Only generate outline if one was not passed in
        concepts = await create_course_concepts(course_name, revision)
        if concepts is None:
            return

        outline, queries = await create_course_outline(course_name, concepts, outline_items, revision)

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
            context = await query_course_context(model, queries, context_outline)
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


@ray.remote
def process_courses(model, courses, args):
    try:
        return asyncio.run(_process_courses(model, courses, args))
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating courses: {e}")

@ray.remote
def process_course(model, course, args):
    try:
        return asyncio.run(_process_course(model, course, args))
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating course: {e}")


def load_topics(in_file: str):
    with open(os.path.join(settings.DATA_DIR, in_file)) as f:
        if in_file.endswith(".json"):
            topics = json.load(f)
        elif in_file.endswith(".jsonl"):
            lines = list(f)
            topics = []
            for line in lines:
                topics.append(json.loads(line))
        else:
            raise Exception(f"Unknown file type for {in_file}")

    random.seed(1)
    random.shuffle(topics)

    return topics


def to_iterator(obj_ids):
    while obj_ids:
        done, obj_ids = ray.wait(obj_ids)
        yield ray.get(done[0])


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
    topics = []
    in_files = args.in_file.split(",")
    for in_file in in_files:
        topics += load_topics(in_file.strip())

    if args.max is not None:
        topics = topics[:args.max]

    # Everything is cached, so exact duplicates will result in the same output
    topics = exact_deduplicate(topics)

    total_processes = args.workers
    func = process_course

    if settings.THREADS_PER_WORKER > 1:
        # group topics into batches of settings.THREADS_PER_WORKER
        topics = [topics[i:i + settings.THREADS_PER_WORKER] for i in
                          range(0, len(topics), settings.THREADS_PER_WORKER)]
        total_processes = math.ceil(args.workers / settings.THREADS_PER_WORKER)
        func = process_courses

    ray.init(num_cpus=total_processes, storage=settings.RAY_CACHE_PATH, _temp_dir=settings.RAY_CACHE_PATH, dashboard_host=settings.RAY_DASHBOARD_HOST)

    model = SentenceTransformer("thenlper/gte-small")
    model_ref = ray.put(model)

    print(f"Generating {len(topics)} course batches with {total_processes} processes from filename(s) {in_files}")
    futures = [func.remote(model_ref, batch, args) for batch in topics]

    courses = []
    for x in tqdm(to_iterator(futures), total=len(futures)):
        courses.append(x)

    if settings.THREADS_PER_WORKER > 1:
        # Flatten courses list
        courses = [course for batch in courses for course in batch]

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




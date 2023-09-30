import asyncio
import math
from typing import Optional
import argparse

from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from app.db.session import get_session
from app.db.tables import * # Needed to avoid errors with table imports
from app.course.tasks import create_course_concepts, create_course_outline, query_course_context
from app.course.models import load_cached_course, Course
from app.lesson.tasks import generate_lesson
from app.lesson.output import render_components_to_output_markdown
from app.settings import settings
import json
import os
import random
import ray

from app.util import debug_print_trace, exact_deduplicate


async def query_course(topic: str, model: str):
    lesson = await load_cached_course(model, topic)
    return lesson


async def save_course(course: Course):
    async with get_session() as db:
        db.add(course)
        await db.commit()


def get_json_data_from_course(course: Course):
    json_data = {
        "topic": course.topic,
        "model": settings.LLM_TYPE,
        "concepts": course.concepts,
        "outline": course.outline,
        "markdown": course.markdown,
        "components": course.components
    }
    return json.dumps(json_data)


async def generate_single_course(model, course_name, outline_items=12):
    components = ["exercise", "example"]

    course = await query_course(course_name, settings.LLM_TYPE)
    if course is not None:
        await asyncio.sleep(.01) # Sleep to avoid high CPU usage with many workers
        return course

    topic, concepts = await create_course_concepts(course_name)
    if concepts is None:
        return

    outline, queries = await create_course_outline(course_name, concepts, outline_items)

    if outline is None:
        return

    # Remove the intro if it exists
    if "intro" in outline[0].lower():
        outline = outline[1:]

    context = None
    if queries is not None:
        try:
            # Up to one retrieved passage per outline item
            context = await query_course_context(model, queries, outline)
        except Exception as e:
            debug_print_trace()
            print(f"Error generating context for {course_name}: {e}")

    components = await generate_lesson(course_name, components, outline, research_notes=context)
    if components is None:
        return

    md = render_components_to_output_markdown(components)

    flat_context = None if context is None else [item.json() for item in context]
    course = Course(topic=course_name, model=settings.LLM_TYPE, outline=outline, concepts=concepts, markdown=md, components=components, context=flat_context)
    await save_course(course)

    return course


async def _process_course(model, topic):
    try:
        return await generate_single_course(model, topic)
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating course: {e}")


async def _process_courses(model, courses):
    processes = [_process_course(model, course) for course in courses]
    return await asyncio.gather(*processes)

@ray.remote
def process_courses(model, courses):
    try:
        return asyncio.run(_process_courses(model, courses))
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating courses: {e}")

@ray.remote
def process_course(model, course):
    try:
        return asyncio.run(_process_course(model, course))
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating course: {e}")


def load_topics(in_file: str):
    with open(os.path.join(settings.DATA_DIR, in_file)) as f:
        topics = json.load(f)

    random.seed(1)
    random.shuffle(topics)

    return topics


def to_iterator(obj_ids):
    while obj_ids:
        done, obj_ids = ray.wait(obj_ids)
        yield ray.get(done[0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Given a topic file, generate synthetic books.")
    parser.add_argument("in_file", help="Input filename (flat json list).  One file or a comma-separated list of files.")
    parser.add_argument("out_file", help="Output filename (jsonl)")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of courses to generate")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers to use")
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

    ray.init(num_cpus=total_processes, storage=settings.RAY_CACHE_PATH, _temp_dir=settings.RAY_CACHE_PATH)

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    model_ref = ray.put(model)

    print(f"Generating {len(topics)} course batches with {total_processes} processes")
    futures = [func.remote(model_ref, batch) for batch in topics]

    courses = []
    for x in tqdm(to_iterator(futures), total=len(futures)):
        courses.append(x)

    if settings.THREADS_PER_WORKER > 1:
        # Flatten courses list
        courses = [course for batch in courses for course in batch]


    course_count = 0
    with open(os.path.join(settings.DATA_DIR, args.out_file), "w+") as f:
        for course, topic in zip(courses, topics):
            # Filter out courses that didn't generate properly
            if course is None or isinstance(course, Exception):
                continue

            if course.markdown is None or len(course.markdown) == 0:
                continue

            course_count += 1
            json_data = get_json_data_from_course(course)
            f.write(json_data + '\n')
    print(f"Generated {course_count} courses")
    ray.shutdown()




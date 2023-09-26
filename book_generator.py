import asyncio
import traceback
from dataclasses import dataclass
from typing import List, Dict, Optional
import argparse

from pydantic import BaseModel

from app.db.session import get_session
from app.db.tables import * # Needed to avoid errors with table imports
from app.course.tasks import create_course_concepts, create_course_outline, query_course_context
from app.course.models import load_cached_course, Course
from app.lesson.tasks import generate_lesson
from app.lesson.output import render_components_to_output_markdown
from tqdm.contrib.concurrent import process_map
from app.settings import settings
import json
import os
import random

from app.util import debug_print_trace


async def query_course(topic: str, model: str):
    lesson = await load_cached_course(model, topic)
    return lesson


async def save_course(course: Course):
    async with get_session() as db:
        db.add(course)
        await db.commit()


async def generate_single_course(course_name, outline_items=12):
    components = ["exercise", "example"]

    course = await query_course(course_name, settings.LLM_TYPE)
    if course is not None:
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
            context = await query_course_context(queries, outline)
        except Exception as e:
            debug_print_trace()
            print(f"Error generating context for {course_name}: {e}")

    components = await generate_lesson(course_name, components, outline, research_notes=context)
    if components is None:
        return

    md = render_components_to_output_markdown(components)

    flat_context = None if context is None else [item.json() for item in context]
    course = Course(topic=topic, model=settings.LLM_TYPE, outline=outline, concepts=concepts, markdown=md, components=components, context=flat_context)
    await save_course(course)
    return course


def process_course(course):
    try:
        return asyncio.run(generate_single_course(course))
    except Exception as e:
        debug_print_trace()
        print(f"Unhandled error generating course: {e}")


def load_topics(in_file: str, max_topics: Optional[str]):
    with open(os.path.join(settings.DATA_DIR, in_file)) as f:
        topics = json.load(f)

    random.seed(1)
    random.shuffle(topics)

    if max_topics is not None:
        topics = topics[:max_topics]

    return topics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Given a topic file, generate synthetic books.")
    parser.add_argument("in_file", help="Input filename (flat json list)")
    parser.add_argument("out_file", help="Output filename (jsonl)")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of courses to generate")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers to use")
    args = parser.parse_args()

    topics = load_topics(args.in_file, max_topics=args.max)

    courses = process_map(process_course, topics, max_workers=args.workers, chunksize=1)

    with open(os.path.join(settings.DATA_DIR, args.out_file), "w+") as f:
        for course, topic in zip(courses, topics):

            # Filter out courses that didn't generate properly
            if course is None or course.markdown is None or len(course.markdown) == 0:
                continue
            json_data = {
                "topic": topic,
                "model": settings.LLM_TYPE,
                "concepts": course.concepts,
                "outline": course.outline,
                "markdown": course.markdown
            }
            f.write(json.dumps(json_data) + '\n')




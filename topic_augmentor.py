import traceback
from copy import copy
import argparse

from app.settings import settings
import json
import os
from app.llm.generators.topic import generate_topic, generate_specific_topic
from app.course.embeddings import dedup_list
import asyncio
from tqdm import tqdm

from app.util import debug_print_trace


def load_processed_titles(file_name: str):
    with open(os.path.join(settings.DATA_DIR, file_name)) as f:
        titles = json.load(f)
    return titles


async def generate_topics(title):
    topics = await generate_topic(title)
    return topics

async def generate_specific_topics(title, domain=None):
    topics = await generate_specific_topic(title, domain)
    return topics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Augment book titles with synthetic topics, and dedup.")
    parser.add_argument("in_file", help="Input filename (flat json list)")
    parser.add_argument("out_file", help="Output filename (flat json list)")
    parser.add_argument("--domain", help="Specific domain for the topics", default=None, type=str)
    args = parser.parse_args()

    titles = load_processed_titles(args.in_file)

    topics_from_titles = copy(titles)
    for title in tqdm(titles):
        try:
            topics = asyncio.run(generate_topics(title))
            topics_from_titles.extend(topics)
        except Exception as e:
            debug_print_trace()
            print(f"Error generating topic: {e}")

    topics_from_titles = dedup_list(topics_from_titles)
    print(len(topics_from_titles))

    all_topics = copy(topics_from_titles)
    for topic in tqdm(topics_from_titles):
        try:
            topics = asyncio.run(generate_specific_topics(topic, domain=args.domain))
            all_topics.extend(topics)
        except Exception as e:
            debug_print_trace()
            print(f"Error generating specific topic: {e}")

    all_topics = dedup_list(all_topics)

    with open(os.path.join(settings.DATA_DIR, args.out_file), "w+") as f:
        json.dump(all_topics, f, indent=2)

    print(len(all_topics))


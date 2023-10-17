import traceback
import argparse

from app.llm.exceptions import GenerationError
from app.settings import settings
import json
import os
from app.llm.generators.title import generate_title
from app.course.embeddings import dedup_list
import asyncio
from tqdm import tqdm

from app.util import debug_print_trace

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate book titles from a given subject.")
    parser.add_argument("subject", help="Input subject", type=str)
    parser.add_argument("out_file", help="Output filename (flat json list)")
    parser.add_argument("--iterations", default=10, type=int, help="Number of times to generate titles")
    parser.add_argument("--cache", default=True, type=bool, help="Whether to cache the results. Set to false when iterations > 1")
    args = parser.parse_args()

    cache = args.cache

    all_topics = []
    for i in tqdm(range(args.iterations)):
        try:
            topics = asyncio.run(generate_title(args.subject, cache=cache))
            all_topics.extend(topics)
        except GenerationError as e:
            debug_print_trace()
            print(f"Error generating titles {e}")

        # Disable caching for subsequent iterations
        cache = False

    all_topics = dedup_list(all_topics, score_thresh=.95)
    with open(os.path.join(settings.DATA_DIR, args.out_file), "w+") as f:
        json.dump(all_topics, f, indent=2)

    print(len(all_topics))


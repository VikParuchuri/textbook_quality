import argparse

from tqdm.contrib.concurrent import process_map

from app.llm.exceptions import GenerationError, InvalidRequestError
from app.settings import settings
import json
import os
from app.llm.generators.toc import generate_tocs
import asyncio

from app.util import debug_print_trace


async def generate_tocs_async(topic, toc):
    final = await generate_tocs(topic, toc)
    return final


def generate_tocs_sync(topic, toc):
    try:
        return asyncio.run(generate_tocs_async(topic, toc))
    except (GenerationError, InvalidRequestError):
        debug_print_trace()
        print(f"Error generating toc for {topic}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up real ToCs from books.")
    parser.add_argument("in_file", help="Input tocs and titles in jsonl format.  Should be a list of json objects with the keys toc (str) and title (str).", type=str)
    parser.add_argument("out_file", help="Output filename in jsonl format (list of json objects)")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of tocs to generate")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers to use")
    args = parser.parse_args()

    topics = []
    with open(os.path.join(settings.DATA_DIR, args.in_file)) as f:
        lines = list(f)

    for line in lines:
        topics.append(json.loads(line))

    if args.max is not None:
        topics = topics[:args.max]

    new_tocs = process_map(generate_tocs_sync, [t["title"] for t in topics], [t["toc"] for t in topics], max_workers=args.workers, chunksize=1)
    new_tocs = [t for t in new_tocs if t is not None]

    json_tocs = [t.dict() for t in new_tocs]
    with open(os.path.join(settings.DATA_DIR, args.out_file), "w+") as f:
        for line in json_tocs:
            f.write(json.dumps(line))
            f.write("\n")

    print(f"Generated {len(json_tocs)} tocs")


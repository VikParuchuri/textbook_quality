import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from app.settings import settings
import json
import datasets
from transformers import AutoTokenizer


tokenizer = AutoTokenizer.from_pretrained("vikp/code_llama_7b_hf")


def book_stats(filename: str):
    courses = []

    with open(os.path.join(settings.DATA_DIR, filename)) as f:
        lines = list(f)
        for line in lines:
            courses.append(json.loads(line))

    data = datasets.Dataset.from_list(courses)

    tokens = tokenizer(data["markdown"])
    total = 0

    for i in range(len(data)):
        total += len(tokens[i])

    print(f"Total books: {len(data)}")
    print(f"Total tokens: {total}")
    print(f"Tokens per textbook: {total / len(data)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse and print stats about generated textbooks.")
    parser.add_argument("in_file", help="Input filename (flat json list)")
    args = parser.parse_args()

    book_stats(args.in_file)




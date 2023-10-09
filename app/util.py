import traceback
from enum import Enum
import regex

import ftfy

from app.settings import settings


class BaseEnum(Enum):
    def __str__(self):
        return str(self.value)


def extract_only_json_dict(text: str) -> str:
    # Extract the first top-level JSON object
    pattern = r'({(?:[^{}]|(?R))*})'
    match = regex.search(pattern, text, regex.DOTALL)
    if match:
        return match.group(0)

    return text


def extract_only_json_list(text: str) -> str:
    # Extract the first top-level JSON object
    pattern = r'(\[(?:[^\[\]]|(?R))*\])'
    match = regex.search(pattern, text, regex.DOTALL)
    if match:
        return match.group(0)

    return text


def fix_unicode_text(text: str) -> str:
    fixed = ftfy.fix_text(text)
    fixed = fixed.encode("utf-8", errors="ignore").decode("utf-8")
    fixed = fixed.replace("\ufffd", " ")
    return fixed


def debug_print_trace():
    if settings.DEBUG:
        print(traceback.format_exc())


def exact_deduplicate(topics):
    result = []
    for line in topics:
        if not isinstance(line, (str, dict)):
            continue

        if isinstance(line, dict):
            topic = line["topic"]
        else:
            topic = line

        if topic not in result:
            result.append(line)
    return result

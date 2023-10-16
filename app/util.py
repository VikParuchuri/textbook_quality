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


def smart_split(s, max_remove=settings.CONTEXT_BLOCK_SIZE // 4):
    # Split into chunks based on actual word boundaries
    s_len = len(s)

    # Don't remove anything if string is too short
    if max_remove > s_len:
        return s, ""

    delimiter = None
    max_len = 0

    for split_delimiter in ["\n\n", ". ", "! ", "? ", "}\n", ":\n", ")\n", ".\n", "!\n", "?\n"]:
        split_str = s.rsplit(split_delimiter, 1)
        if len(split_str) > 1 and len(split_str[0]) > max_len:
            max_len = len(split_str[0])
            delimiter = split_delimiter

    if delimiter is not None and max_len > s_len - max_remove:
        return s.rsplit(delimiter, 1)

    # Try \n as a last resort
    str_split = s.rsplit("\n", 1)
    if len(split_str) > 1 and len(split_str[0]) > max_len:
        max_len = len(str_split[0])
        delimiter = "\n"

    if delimiter is None:
        return s, ""

    if max_len < s_len - max_remove:
        return s, ""

    return s.rsplit(delimiter, 1)

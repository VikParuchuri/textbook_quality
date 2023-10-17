from typing import List
from ftfy import fix_text

from app.services.schemas import SearchData
from app.settings import settings


def has_enough_alphanumeric_chars(line):
    return sum(c.isalnum() for c in line) >= 3 or not line.strip()


def chunk_documents(documents: List[str]):
    search_data = []
    for document in documents:
        content = []
        curr_block = ""
        document = fix_text(document)
        document = "\n".join(line for line in document.split("\n") if has_enough_alphanumeric_chars(line))
        total_lines = len(document.split("\n"))
        for i, line in enumerate(document.split("\n")):
            if i < total_lines * .15 or i > total_lines * .85:
                # Ignore starting and closing lines (toc, references, etc)
                continue

            curr_block += line + "\n"
            if len(curr_block) > settings.CONTEXT_BLOCK_SIZE:
                content.append(curr_block.strip())
                curr_block = ""

        if curr_block.strip():
            content.append(curr_block)

        data = SearchData(content=content, query=document[:20], kind="document")
        search_data.append(data)
    return search_data
import asyncio
from typing import List

from pydantic import BaseModel

from app.services.exceptions import ResponseError, RequestError
from app.services.schemas import ServiceInfo, SearchData
from app.services.service import get_service_response
from app.settings import settings
from app.services.adaptors.custom_search import wiki_search_settings


async def search_wiki(queries: List[str]) -> List[SearchData]:
    coroutines = [_search_wiki(query) for query in queries]

    # Run queries in parallel
    results = await asyncio.gather(*coroutines)

    # Filter results to only unique wiki entries
    filtered = []
    seen_text = []
    for r in results:
        text = r.content[0]
        if text not in seen_text:
            seen_text.append(text)
            filtered.append(r)
    return filtered


async def _search_wiki(query):
    if not settings.CUSTOM_SEARCH_SERVER:
        return []

    service_info = ServiceInfo(query=query)
    try:
        response = await get_service_response(wiki_search_settings, service_info, cache=False)
    except (RequestError, ResponseError):
        return []

    content = []
    curr_block = ""
    for line in response["text"].split("\n"):
        curr_block += line + "\n"
        if len(curr_block) > settings.CONTEXT_BLOCK_SIZE:
            content.append(curr_block.strip())
            curr_block = ""

    if curr_block:
        content.append(curr_block.strip())

    return SearchData(content=content, query=query, kind="wiki")
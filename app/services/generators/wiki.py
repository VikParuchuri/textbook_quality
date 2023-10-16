import asyncio
from typing import List

from pydantic import BaseModel

from app.services.exceptions import ResponseError, RequestError
from app.services.schemas import ServiceInfo, SearchData
from app.services.service import get_service_response
from app.settings import settings
from app.services.adaptors.custom_search import wiki_search_settings


async def search_wiki(queries: List[str]) -> List[SearchData]:
    results = await _search_wiki(queries)

    # Filter results to only unique wiki entries
    filtered = []
    seen_text = []
    for r in results:
        text = r.content[0]
        if text not in seen_text:
            seen_text.append(text)
            filtered.append(r)
    return filtered


async def _search_wiki(queries: List[str]) -> List[SearchData]:
    if not settings.CUSTOM_SEARCH_SERVER:
        return []

    service_info = ServiceInfo(queries=queries)
    try:
        response = await get_service_response(wiki_search_settings, service_info, cache=False)
    except (RequestError, ResponseError, KeyError):
        return []

    search_data = []
    for i, item in enumerate(response["text"]):
        content = []
        curr_block = ""
        for line in item.split("\n"):
            curr_block += line + "\n"
            if len(curr_block) > settings.CONTEXT_BLOCK_SIZE:
                content.append(curr_block.strip())
                curr_block = ""

        if curr_block.strip():
            content.append(curr_block)

        data = SearchData(content=content, query=queries[i], kind="wiki")
        search_data.append(data)
    return search_data
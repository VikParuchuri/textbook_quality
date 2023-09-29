import asyncio
import math
import os
from itertools import chain
from typing import List, Optional

import fitz as pymupdf
from aiohttp import ClientPayloadError
from fitz import FileDataError
from pydantic import BaseModel

from app.db.session import get_session
from app.services.adaptors.serpapi import serpapi_pdf_search_settings
from app.services.adaptors.serply import serply_pdf_search_settings
from app.services.dependencies import get_stored_url
from app.services.exceptions import ProcessingError
from app.services.models import store_scraped_data
from app.services.network import download_and_save
from app.services.schemas import PDFData, ServiceInfo, ServiceNames
from app.services.service import get_service_response
from app.settings import settings

BLOCK_SIZE = 2000  # Characters per text block

SEARCH_SETTINGS = {
    "serply": serply_pdf_search_settings,
    "serpapi": serpapi_pdf_search_settings,
}

pdf_service_settings = SEARCH_SETTINGS.get(
    settings.SEARCH_BACKEND
)  # Get the right settings for search

if not pdf_service_settings:
    print("Not using retrieval.  Invalid search backend or no backend set.")


class PDFSearchResult(BaseModel):
    link: str
    title: str
    description: str
    query: str


async def search_pdfs(queries: List[str], max_count=5) -> List[PDFSearchResult]:
    coroutines = [search_pdf(query, max_count) for query in queries]

    # Run sequentially to save DB connections
    results = []
    for task in coroutines:
        results.append(await task)

    results = list(chain.from_iterable(results))

    # Filter results to only unique links
    filtered = []
    seen_links = []
    seen_titles = []
    for r in results:
        link = r.link
        title = r.title
        if link not in seen_links and title not in seen_titles:
            seen_links.append(link)
            seen_titles.append(title)
            filtered.append(r)
    return filtered


async def search_pdf(query: str, max_count) -> List[PDFSearchResult]:
    if not pdf_service_settings:
        return []

    service_info = ServiceInfo(query=query)

    # Run google search for pdf
    response = await get_service_response(pdf_service_settings, service_info)

    pdf_links = []
    for i in range(10):
        try:
            if pdf_service_settings.name == ServiceNames.serply:
                pdf_result = response["results"][i]
                pdf_description = pdf_result["description"]
            else:
                pdf_result = response["organic_results"][i]
                pdf_description = pdf_result["snippet"]

            pdf_link = pdf_result["link"]
            pdf_title = pdf_result["title"]
            if not pdf_link or not pdf_link.endswith(".pdf"):
                continue
        except (KeyError, IndexError):
            continue

        search_result = PDFSearchResult(
            link=pdf_link, title=pdf_title, description=pdf_description, query=query
        )
        pdf_links.append(search_result)
        if len(pdf_links) >= max_count:
            break
    return pdf_links


async def download_and_parse_pdfs(
    search_results: List[PDFSearchResult],
) -> List[PDFData]:
    # Query if PDFs have already been downloaded and stored
    pdf_paths = []
    async with get_session() as db:
        for search_result in search_results:
            pdf_paths.append(await get_stored_url(db, search_result.link))

    coroutines = [
        download_and_parse_pdf(search_result, pdf_path) for search_result, pdf_path in zip(search_results, pdf_paths)
    ]
    results = await asyncio.gather(*coroutines)
    results = [result for result in results if result]

    # Store all scraping results
    async with get_session() as db:
        for result in results:
            if not result.stored:
                store_scraped_data(db, result.link, result.pdf_path)
        await db.commit()
    return results


async def download_and_parse_pdf(search_result: PDFSearchResult, pdf_path: Optional[str]) -> Optional[PDFData]:
    stored = False
    if pdf_path:
        with open(os.path.join(settings.PDF_CACHE_DIR, pdf_path), "rb") as f:
            pdf_data = f.read()
        stored = True
    else:
        try:
            # Download pdf, save to filesystem
            pdf_path, pdf_data = await download_and_save(search_result.link)
        except ProcessingError as e:
            # This happens when pdf is too large
            return
        except ClientPayloadError as e:
            return
        except Exception as e:
            return

    try:
        pdf_content = parse_pdf(pdf_data)
    except FileDataError:
        return

    pdf_cls = PDFData(
        pdf_path=pdf_path,
        link=search_result.link,
        title=search_result.title,
        description=search_result.description,
        content=pdf_content,
        query=search_result.query,
        stored=stored,
    )

    # Bail out if we don't have enough text or blocks in our pdf
    if len(pdf_cls.content) < 6:
        return

    all_content = "".join(pdf_cls.content)
    if len(all_content) < 2000:
        return

    return pdf_cls


def parse_pdf(data) -> List[str]:
    with pymupdf.open(stream=data) as doc:
        blocks = []
        for page in doc:
            blocks += page.get_text(
                "blocks",
                sort=True,
                flags=~pymupdf.TEXT_PRESERVE_LIGATURES
                & pymupdf.TEXT_PRESERVE_WHITESPACE
                & ~pymupdf.TEXT_PRESERVE_IMAGES
                & ~pymupdf.TEXT_INHIBIT_SPACES
                & pymupdf.TEXT_DEHYPHENATE
                & pymupdf.TEXT_MEDIABOX_CLIP,
            )
    start = math.floor(len(blocks) * 0.15)
    end = math.ceil(len(blocks) * 0.85)

    blocks = blocks[start:end]
    parsed_blocks = []
    block = ""
    for i, b in enumerate(blocks):
        block += b[4]
        if len(block) > BLOCK_SIZE:
            parsed_blocks.append(block)
            block = ""
    parsed_blocks.append(block)
    return parsed_blocks

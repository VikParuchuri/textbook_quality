import os
import secrets
from io import BytesIO

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError, ClientOSError

from app.services.exceptions import ProcessingError
from app.settings import settings


def generate_pdf_name():
    return f"{secrets.token_urlsafe(32)}.pdf"


async def download_file_safely(url: str) -> bytes:
    try:
        data = BytesIO()
        total_len = 0
        chunk_size = 1024
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                content_length = int(response.headers.get("content-length", 0))
                if content_length > settings.MAX_DOWNLOAD_SIZE:
                    raise ProcessingError(f"File too large: {url}")

                async for chunk in response.content.iter_chunked(chunk_size):
                    total_len += chunk_size
                    data.write(chunk)
                    if total_len > settings.MAX_DOWNLOAD_SIZE:
                        raise ProcessingError(f"Download exceeded max size: {url}")
    except (ConnectionError, ClientConnectorError, ClientOSError):
        raise ProcessingError(f"Failed to download file: {url}")

    return data.getvalue()


async def download_and_save(url: str):
    data = await download_file_safely(url)

    pdf_name = generate_pdf_name()
    file_path = os.path.join(settings.PDF_CACHE_DIR, pdf_name)
    with open(file_path, "wb") as f:
        f.write(data)
    return pdf_name, data

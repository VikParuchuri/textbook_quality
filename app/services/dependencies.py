from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.services.models import ScrapedData, ServiceResponse


async def get_stored_urls(urls: List[str]) -> List[Optional[str]]:
    async with get_session() as db:
        query = await db.exec(select(ScrapedData).where(ScrapedData.source.in_(urls)))
        stored_urls = query.all()
    return_data = {}
    for url in urls:
        return_data[url] = None
        for stored_url in stored_urls:
            if url == stored_url.source:
                return_data[url] = stored_url.uploaded
    return [return_data[url] for url in urls]


async def get_service_response_model(name: str, hex: str):
    async with get_session() as db:
        query = await db.exec(
            select(ServiceResponse).where(
                ServiceResponse.hash == hex, ServiceResponse.name == name
            )
        )
        service_model = query.first()
    return service_model

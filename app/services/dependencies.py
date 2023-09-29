from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.services.models import ScrapedData, ServiceResponse


async def get_stored_url(db: AsyncSession, url: str) -> str | None:
    query = await db.exec(select(ScrapedData).where(ScrapedData.source == url))
    stored_url = query.first()
    if stored_url:
        return stored_url.uploaded


async def get_service_response_model(name: str, hex: str):
    async with get_session() as db:
        query = await db.exec(
            select(ServiceResponse).where(
                ServiceResponse.hash == hex, ServiceResponse.name == name
            )
        )
        service_model = query.first()
    return service_model

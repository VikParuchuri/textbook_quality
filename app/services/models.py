from pydantic import validator
from sqlmodel import JSON, Column, Field, UniqueConstraint

from app.db.base_model import BaseDBModel
from app.db.session import get_session
from app.services.schemas import ServiceInfo, ServiceNames


class ServiceResponse(BaseDBModel, table=True):
    __table_args__ = (UniqueConstraint("hash", "name", name="unique_hash_name"),)
    hash: str = Field(index=True)
    request: ServiceInfo = Field(sa_column=Column(JSON), default=dict(), nullable=False)
    response: dict = Field(sa_column=Column(JSON), default=dict(), nullable=False)
    name: ServiceNames

    @validator("request")
    def gen_request_to_dict(cls, val: ServiceInfo):
        return val.json()


class ScrapedData(BaseDBModel, table=True):
    source: str = Field(index=True, unique=True)
    uploaded: str
    extra: dict | None = Field(sa_column=Column(JSON), default=dict(), nullable=True)


async def store_scraped_data(source: str, uploaded: str):
    async with get_session() as db:
        data = ScrapedData(source=source, uploaded=uploaded)
        db.add(data)
        await db.commit()

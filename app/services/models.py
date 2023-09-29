from pydantic import validator
from sqlmodel import JSON, Column, Field, UniqueConstraint, Session
from sqlmodel.ext.asyncio.session import AsyncSession

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


def store_scraped_data(db: AsyncSession, source: str, uploaded: str):
    data = ScrapedData(source=source, uploaded=uploaded)
    db.add(data)

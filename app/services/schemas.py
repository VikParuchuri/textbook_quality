from typing import List, Optional

from pydantic import BaseModel

from app.util import BaseEnum


class ServiceNames(str, BaseEnum):
    serply = "serply"
    serpapi = "serpapi"


class ServiceSettings(BaseModel):
    name: ServiceNames
    type: str


class ServiceInfo(BaseModel):
    query: Optional[str] = None
    content: Optional[str] = None


class PDFData(BaseModel):
    pdf_path: str
    link: str
    text_link: str | None = None
    title: str
    description: str
    content: List[str]
    query: str | None = None

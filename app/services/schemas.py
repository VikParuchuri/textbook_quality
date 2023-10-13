from typing import List, Optional

from pydantic import BaseModel

from app.util import BaseEnum


class ServiceNames(str, BaseEnum):
    serply = "serply"
    serpapi = "serpapi"
    custom = "custom"


class ServiceSettings(BaseModel):
    name: ServiceNames
    type: str


class ServiceInfo(BaseModel):
    query: Optional[str] = None
    content: Optional[str] = None


class SearchData(BaseModel):
    content: List[str]
    query: str
    stored: bool = False
    pdf_path: Optional[str] = None
    link: Optional[str] = None
    title: Optional[str] = None
    kind: str

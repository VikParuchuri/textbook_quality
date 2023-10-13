from typing import List

from pydantic import BaseModel


class ResearchNote(BaseModel):
    content: str
    outline_items: List[int]
    kind: str

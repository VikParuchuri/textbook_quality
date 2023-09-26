from pydantic import BaseModel


class ResearchNote(BaseModel):
    content: str
    title: str
    link: str
    description: str

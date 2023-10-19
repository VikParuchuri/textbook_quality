import json
from typing import List

from pydantic import validator
from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, select

from app.components.schemas import AllLessonComponentData
from app.db.base_model import BaseDBModel
from app.db.session import get_session
from app.course.schemas import ResearchNote


class Course(BaseDBModel, table=True):
    __table_args__ = (UniqueConstraint("topic", "model", "version", name="unique_topic_model_version"),)

    model: str
    topic: str
    outline: List[str] = Field(sa_column=Column(JSON), default=list())
    concepts: List[str] = Field(sa_column=Column(JSON), default=list())
    potential_outline_items: List[str] = Field(sa_column=Column(JSON), default=list())
    markdown: str = Field(sa_column=Column(JSON), default=list())
    components: List[AllLessonComponentData] = Field(
        sa_column=Column(JSON), default=list()
    )
    queries: List[str] = Field(sa_column=Column(JSON), default=list())
    context: List[ResearchNote] = Field(sa_column=Column(JSON), default=list())
    version: int = Field(default=1, )

    @validator("context")
    def context_to_dict(cls, val: List[ResearchNote]):
        return [v.json() for v in val]

    @validator("components")
    def components_to_dict(cls, val: List[AllLessonComponentData]):
        return [v.json() for v in val]


async def load_cached_course(model: str, topic: str, revision: int):
    async with get_session() as db:
        query = await db.exec(
            select(Course).where(Course.topic == topic, Course.model == model, Course.version == revision)
        )
        course = query.all()
    if len(course) == 0:
        return None
    course = course[0]

    if course.context is not None:
        course.context = [ResearchNote(**json.loads(v)) for v in course.context]

    return course

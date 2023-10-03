from typing import Literal, Optional, Union

import markdown
from pydantic import BaseModel, validator

from app.settings import settings
from app.util import BaseEnum


class LessonComponentData(BaseModel):
    key: str
    type: settings.VALID_COMPONENTS  # these are the component types
    markdown: str = ""
    version: int = 1

class MarkdownComponentData(LessonComponentData):
    type: Literal["text", "example", "diagram", "section"]

    @validator("markdown")
    def validate_markdown(cls, value):
        try:
            # Try to parse the text as markdown to html
            markdown.markdown(value)
        except Exception:
            # If parsing fails, raise a validation error
            raise ValueError("Text must be valid markdown")
        return value


class ExerciseModes(str, BaseEnum):
    short_answer = "short_answer"
    code = "code"


class ExerciseComponentData(LessonComponentData):
    type: Literal["exercise"] = "exercise"
    markdown: Optional[str]
    instructions: Optional[str]
    solution: Optional[str]
    mode: Optional[ExerciseModes] = ExerciseModes.short_answer


AllLessonComponentData = Union[
    ExerciseComponentData,
    MarkdownComponentData,
]


class ComponentNames(str, BaseEnum):
    text = "text"
    example = "example"
    exercise = "exercise"
    section = "section"


COMPONENT_MAP = {
    ComponentNames.text: MarkdownComponentData,
    ComponentNames.example: MarkdownComponentData,
    ComponentNames.exercise: ExerciseComponentData,
    ComponentNames.section: MarkdownComponentData,
}

COMPONENT_VERSION = 1

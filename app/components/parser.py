import re
import secrets
from typing import get_args

from app.components.schemas import (
    COMPONENT_MAP,
    COMPONENT_VERSION,
    ComponentNames,
    ExerciseModes,
)
from app.settings import settings


def parse_single_component(component_type: str, markdown: str, key: str = None):
    component_cls = COMPONENT_MAP[component_type]
    component_data = {
        "key": key if key else generate_component_key(),
        "version": COMPONENT_VERSION,
        "type": component_type,
    }
    match component_type:
        case ComponentNames.exercise:
            exercise_data = re.split(r"\nAnswer\n|\nAnswer:\n|\nAnswer: ", markdown)
            match len(exercise_data):
                case 1:
                    instructions, answer = exercise_data[0], None
                case 2:
                    instructions, answer = exercise_data
                    answer = answer.strip()
                case _:
                    instructions = exercise_data[0]
                    answer = "\n".join(exercise_data[1:])
            instructions = instructions.strip()
            instructions = (
                instructions.replace("Instructions\n", "")
                .replace("\nExercise\n", "")
                .replace("\nExercise:\n", "")
            )

            mode = (
                ExerciseModes.code
                if answer and "```" in answer
                else ExerciseModes.short_answer
            )

            new_component = component_cls(
                markdown=markdown,
                instructions=instructions,
                solution=answer,
                mode=mode,
                **component_data,
            )
        case ComponentNames.section:
            new_component = component_cls(markdown=markdown, **component_data)
        case _:
            if component_type not in list(
                get_args(settings.VALID_GENERATED_COMPONENTS)
            ):
                raise ValueError(f"Invalid component type: {component_type}")
            new_component = component_cls(markdown=markdown, **component_data)
    return new_component


def generate_component_key() -> str:
    return f"ek-{secrets.token_hex(16)}"

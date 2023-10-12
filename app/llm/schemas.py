from typing import List, Optional

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    tokens: int


class GenerationSettings(BaseModel):
    temperature: float
    max_tokens: int
    timeout: int
    stop_sequences: Optional[List[str]]
    prompt_type: str
    component_name: Optional[str]
    model: Optional[str]

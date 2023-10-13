import os
from typing import Literal, Optional, List

from dotenv import find_dotenv
from pydantic import BaseSettings


class Settings(BaseSettings):
    # Path settings
    BASE_DIR: str = os.path.abspath(os.path.dirname(__file__))
    PDF_CACHE_DIR = os.path.join(BASE_DIR, "cache")  # Where to save pdfs
    DATA_DIR = os.path.join(BASE_DIR, "data")  # Where to save data
    PROMPT_TEMPLATE_DIR: str = os.path.join(BASE_DIR, "llm", "templates")
    EXAMPLE_JSON_DIR: str = os.path.join(BASE_DIR, "llm", "examples")

    # Database
    DATABASE_URL: str = "postgresql://localhost/textbook"
    DEBUG: bool = False

    # Content
    SECTIONS_PER_LESSON: int = 30  # Lower this to make books shorter
    SECTIONS_PER_GENERATION: int = 5 # How many sections to generate in one prompt
    MAX_DOWNLOAD_SIZE: int = 6 * 1024 * 1024  # Max pdf size to download, 6 MB
    FINETUNED: bool = False # If we're using a finetuned textbook gen model
    INCLUDE_EXAMPLES: bool = (
        True  # Include examples in prompts, False with custom model
    )

    # LLM
    LLM_TYPES = {
        "gpt-3.5-turbo": {"max_tokens": 4097},
        "gpt-3.5-turbo-16k": {"max_tokens": 16384},
        "gpt-3.5-turbo-instruct": {"max_tokens": 4097},
        "llama": {"max_tokens": 8192},
        "gpt-4": {"max_tokens": 8192},
        "gpt-4-32k": {"max_tokens": 32768},
    }

    LLM_TEMPERATURE: float = 0.5
    LLM_TIMEOUT: int = 480
    LLM_MAX_RESPONSE_TOKENS: int = 2048
    OPENAI_KEY: str = ""
    OPENAI_BASE_URL: Optional[str] = None
    LLM_TYPE: str = "gpt-3.5-turbo"
    LLM_INSTRUCT_TYPE: str = "gpt-3.5-turbo-instruct"
    LLM_EXTENDED_TYPE: str = "gpt-3.5-turbo-16k"

    # Generation
    VALID_GENERATED_COMPONENTS = Literal["text", "example", "exercise", "section"]
    VALID_COMPONENTS = Literal["text", "example", "exercise", "section"]

    # Retrieval backend service
    SERPLY_KEY: str = ""
    SERPAPI_KEY: str = ""
    SEARCH_BACKEND: Optional[str] = "serply"
    CUSTOM_SEARCH_SERVER: Optional[str] = None
    CUSTOM_SEARCH_USER: Optional[str] = None
    CUSTOM_SEARCH_PASSWORD: Optional[str] = None
    CUSTOM_SEARCH_TYPES: Optional[List[str]] = ["wiki"]
    CONTEXT_BLOCK_SIZE: int = 2200  # Characters per text block

    # General
    THREADS_PER_WORKER: int = 1 # How many threads to use per worker process to save RAM
    RAY_CACHE_PATH: Optional[str] = None # Where to save ray cache
    RAY_DASHBOARD_HOST: str = "127.0.0.1"
    RAY_CORES_PER_WORKER = 1 # How many cpu cores to allocate per worker

    class Config:
        env_file = find_dotenv("local.env")


settings = Settings()

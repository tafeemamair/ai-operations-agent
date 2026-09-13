"""Isolated model configuration for AI Operations Agent.

All model-specific parameters, API credentials, and environment overrides
are consolidated here to keep business logic and agent tools decoupled
from model settings.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelSettings:
    """Settings and parameters for the agent language model."""

    model_name: str
    api_key: Optional[str]
    temperature: float = 0.2
    max_tokens: Optional[int] = 4096


def get_model_settings() -> ModelSettings:
    """Retrieve model settings configured via environment variables."""
    return ModelSettings(
        model_name=os.getenv("OPENAI_MODEL", "gpt-4o"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
        if os.getenv("OPENAI_MAX_TOKENS")
        else None,
    )


def has_api_key() -> bool:
    """Check if a valid OpenAI API key is configured."""
    key = os.getenv("OPENAI_API_KEY")
    return bool(key and key.strip() and not key.startswith("your_openai"))

"""Provider-neutral types for the LLM layer.

Providers only translate between these types and one vendor SDK. Retries, fallback
between models, batching and normalisation live in `rag.llm.client`.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum


class LLMError(Exception):
    """A provider call failed and retrying will not help."""


class RetryableError(LLMError):
    """Transient failure (rate limit, overload, timeout). Safe to retry."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExhausted(LLMError):
    """The daily/billing quota is used up. Retrying today will not help."""


class BadResponse(LLMError):
    """The model answered, but not in a usable shape (empty, blocked, invalid JSON)."""


class EmbedTask(StrEnum):
    DOCUMENT = 'document'
    QUERY = 'query'


@dataclass(frozen=True)
class Message:
    role: str  # 'user' | 'assistant'
    content: str


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def add(self, other):
        self.calls += other.calls
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens


@dataclass
class Generation:
    text: str
    model: str
    usage: Usage = field(default_factory=Usage)


@dataclass
class StreamEnd:
    """Last item of a provider stream: the complete result."""

    generation: Generation


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    prompt: str
    system: str = ''
    history: tuple[Message, ...] = ()
    json_schema: dict | None = None
    temperature: float = 0.2
    max_output_tokens: int = 2048
    # 'minimal' for quick structured calls (analysis, rerank); '' keeps the model default.
    thinking: str = ''


class Provider(ABC):
    name = ''

    @abstractmethod
    def embed(self, texts, *, model, dimensions, task, titles=None) -> list[list[float]]:
        """One vector per input text, in order."""

    @abstractmethod
    def generate(self, request: GenerateRequest) -> Generation: ...

    @abstractmethod
    def stream(self, request: GenerateRequest) -> Iterator[str | StreamEnd]:
        """Yield text pieces, then exactly one StreamEnd."""

    @abstractmethod
    def read_pdf(self, *, model, pdf, prompt, max_output_tokens) -> Generation:
        """Send a PDF (bytes) with an instruction and return the model's text."""

"""LLM access for the whole app: `get_llm()` returns a fresh client per unit of work."""

import threading

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from rag.llm.base import (  # noqa: F401
    BadResponse,
    EmbedTask,
    LLMError,
    QuotaExhausted,
    RetryableError,
    StreamEnd,
)
from rag.llm.client import LLM

_providers = {}
_lock = threading.Lock()
_override = None


def _build(name):
    if name == 'gemini':
        if not settings.GEMINI_API_KEY:
            raise ImproperlyConfigured('GEMINI_API_KEY is not set.')
        from rag.llm.gemini import GeminiProvider

        return GeminiProvider(settings.GEMINI_API_KEY, settings.LLM_TIMEOUT_SECONDS)
    raise ImproperlyConfigured(f'Unknown LLM provider {name!r}.')


def provider(name):
    """Process-wide provider instance (SDK clients hold connection pools)."""
    with _lock:
        if name not in _providers:
            _providers[name] = _build(name)
        return _providers[name]


def use_provider(fake):
    """Route every get_llm() through `fake` (tests). Pass None to restore."""
    global _override
    _override = fake


def get_llm(**overrides):
    for model_setting in ('CHAT_MODEL', 'FAST_MODEL', 'EMBED_MODEL'):
        if not getattr(settings, model_setting) and _override is None:
            raise ImproperlyConfigured(f'{model_setting} is not set.')
    options = {
        'chat_provider': _override or provider(settings.LLM_PROVIDER),
        'embed_provider': _override or provider(settings.EMBED_PROVIDER),
        'chat_model': settings.CHAT_MODEL or 'fake-chat',
        'fast_model': settings.FAST_MODEL or 'fake-fast',
        'embed_model': settings.EMBED_MODEL or 'fake-embed',
        'dimensions': settings.EMBED_DIMENSIONS,
        'embed_batch_size': settings.EMBED_BATCH_SIZE,
        'max_attempts': settings.LLM_MAX_ATTEMPTS,
    }
    options.update(overrides)
    return LLM(**options)

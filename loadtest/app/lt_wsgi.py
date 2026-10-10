"""WSGI entry for load tests: the real app, with the offline AI made as slow as a real one.

The offline provider answers at once, so a request would free its worker thread far sooner
than in production. Here every stand-in call sleeps for about as long as the real call
takes (medians from production, spread with a log-normal factor), so threads, database
connections and streams are held for a realistic time. The app's own code is untouched.

  LT_CALL_MS        a structured or plain call (question analysis, chat title)
  LT_EMBED_MS       one embedding request
  LT_FIRST_WORD_MS  the answer model's wait before its first word
  OFFLINE_LLM_DELAY_MS  per word after that (the app's own setting)
  LT_JITTER_SIGMA   spread of every delay (0 = fixed)
"""

import os
import random
import time

from backend.wsgi import application  # noqa: F401
from rag.llm.offline import OfflineProvider

CALL = int(os.getenv('LT_CALL_MS', '1500')) / 1000
EMBED = int(os.getenv('LT_EMBED_MS', '600')) / 1000
FIRST_WORD = int(os.getenv('LT_FIRST_WORD_MS', '5500')) / 1000
SIGMA = float(os.getenv('LT_JITTER_SIGMA', '0.35'))


def _wait(median):
    if median > 0:
        time.sleep(median * (random.lognormvariate(0, SIGMA) if SIGMA else 1))  # noqa: S311


_embed, _generate, _stream = (OfflineProvider.embed, OfflineProvider.generate,
                              OfflineProvider.stream)


def embed(self, texts, **options):
    _wait(EMBED)
    return _embed(self, texts, **options)


def generate(self, request):
    _wait(CALL)
    return _generate(self, request)


def stream(self, request):
    _wait(FIRST_WORD)
    yield from _stream(self, request)


OfflineProvider.embed = embed
OfflineProvider.generate = generate
OfflineProvider.stream = stream

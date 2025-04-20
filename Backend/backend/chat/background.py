"""Small fire-and-forget jobs after an answer (titles, memory). Failures only get logged."""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections, connections

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='chat-bg')

# Tests set this to True so jobs run inline and can be asserted on.
RUN_INLINE = False


def _wrap(function, *args):
    close_old_connections()
    try:
        function(*args)
    except Exception:
        logger.exception('Background job %s failed', function.__name__)
    finally:
        connections.close_all()


def submit(function, *args):
    if RUN_INLINE:
        try:
            function(*args)
        except Exception:
            logger.exception('Background job %s failed', function.__name__)
        return
    _executor.submit(_wrap, function, *args)

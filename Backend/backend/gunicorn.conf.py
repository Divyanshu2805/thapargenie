"""Gunicorn settings for the API. Start with: gunicorn backend.wsgi"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = 'gthread'
workers = int(os.getenv('WEB_CONCURRENCY', '2'))
threads = int(os.getenv('GUNICORN_THREADS', '8'))
# Answers stream for up to a minute or two; a hard timeout kills stuck workers only.
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
# Long enough for a streaming answer to finish when a worker is recycled.
graceful_timeout = timeout
keepalive = 5
# Recycle workers now and then so a slow leak in a dependency can't grow forever.
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '2000'))
max_requests_jitter = 200
# Application logs go to stdout in the app's own format; gunicorn's access log would
# duplicate the one written by common.observability.
accesslog = None
errorlog = '-'
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
forwarded_allow_ips = os.getenv('FORWARDED_ALLOW_IPS', '*')


def post_worker_init(worker):
    # Pick up document processing that a restart interrupted.
    from knowledge.jobs import start_recovery

    start_recovery()

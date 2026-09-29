"""A bigger HTTP pool for firebase_admin.

Every API request asks Google whether the session was revoked (api/firebase.py). The
Admin SDK keeps 10 connections per process, so a worker with more threads than that
discards and reopens connections under load ("Connection pool is full"). The SDK has no
setting for this, so the pool of each client it creates is resized here, keeping its
retry policy. The SDK's auth code itself is left untouched.
"""

import logging

logger = logging.getLogger(__name__)

SDK_DEFAULT_POOL = 10


def enlarge_firebase_pool(size):
    if size <= SDK_DEFAULT_POOL:
        return False
    try:
        from firebase_admin import _http_client
    except ImportError:  # pragma: no cover
        return False

    client = _http_client.JsonHttpClient
    if getattr(client, '_pool_enlarged', False):
        return True
    original = client.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        try:
            for prefix in ('https://', 'http://'):
                self.session.get_adapter(prefix).init_poolmanager(size, size)
        except Exception:  # an SDK change must never stop requests from working
            logger.warning('Could not resize the Firebase HTTP pool', exc_info=True)

    client.__init__ = init
    client._pool_enlarged = True
    return True

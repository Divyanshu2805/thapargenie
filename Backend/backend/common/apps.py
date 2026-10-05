from django.apps import AppConfig
from django.conf import settings


class CommonConfig(AppConfig):
    name = 'common'
    verbose_name = 'Common'

    def ready(self):
        from django.db.backends.signals import connection_created

        # Registers the OpenAPI description of the Firebase bearer scheme.
        from common import schema  # noqa: F401
        from common.db import apply_session_settings

        # Timeouts and vector search settings on every new database connection.
        connection_created.connect(apply_session_settings, dispatch_uid='common-session-settings')

        from common import checks  # noqa: F401  (registers the deploy checks)
        from common.firebase_pool import enlarge_firebase_pool

        enlarge_firebase_pool(settings.FIREBASE_HTTP_POOL_SIZE)

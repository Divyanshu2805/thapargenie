from django.apps import AppConfig


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

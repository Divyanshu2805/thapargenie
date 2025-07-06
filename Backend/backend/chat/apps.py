from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'
    verbose_name = 'Chat'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from chat import receivers  # noqa: F401

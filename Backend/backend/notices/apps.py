from django.apps import AppConfig


class NoticesConfig(AppConfig):
    name = 'notices'
    verbose_name = 'Notices'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from knowledge.jobs import register_sweep

        from notices.services import sync_due_documents

        register_sweep(sync_due_documents)

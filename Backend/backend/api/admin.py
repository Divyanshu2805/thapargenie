
from django.contrib import admin

from api.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'actor_kind', 'outcome', 'resource_type')
    list_filter = ('actor_kind', 'outcome', 'action')
    search_fields = ('resource_type', 'resource_id', 'request_id')
    readonly_fields = tuple(field.name for field in AuditEvent._meta.fields)
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

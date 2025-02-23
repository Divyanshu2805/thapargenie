from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from userauths.models import IdentityInvitation, Profile, User


class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'firebase_uid', 'eligibility_state', 'is_staff', 'is_active']
    search_fields = ['email', 'firebase_uid']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'password1', 'password2'),
            },
        ),
    )
    list_filter = ['eligibility_state', 'is_staff', 'is_active']
    fieldsets += (
        (
            'Firebase identity',
            {
                'fields': (
                    'firebase_uid',
                    'eligibility_state',
                    'eligibility_approved_at',
                    'firebase_tokens_valid_after',
                )
            },
        ),
    )
    readonly_fields = (
        'firebase_uid',
        'eligibility_state',
        'eligibility_approved_at',
        'firebase_tokens_valid_after',
        'is_staff',
        'is_superuser',
        'groups',
        'user_permissions',
    )

class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']
    search_fields = ['user__email', 'user__firebase_uid']
    list_filter = ['created_at']


class IdentityInvitationAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'is_active', 'expires_at', 'accepted_at', 'created_at']
    search_fields = ['email']
    list_filter = ['is_active', 'created_at']
    readonly_fields = [
        'id',
        'email',
        'is_active',
        'expires_at',
        'accepted_at',
        'accepted_by',
        'created_by',
        'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(User, UserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(IdentityInvitation, IdentityInvitationAdmin)

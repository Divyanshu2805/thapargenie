from django.urls import path

from access import admin_views as views

urlpatterns = [
    path('invitations/', views.InvitationListView.as_view(), name='admin-invitations'),
    path('invitations/<uuid:invitation_id>/', views.InvitationDetailView.as_view(),
         name='admin-invitation'),
    path('users/', views.UserListView.as_view(), name='admin-users'),
    path('users/<int:user_id>/', views.UserDetailView.as_view(), name='admin-user'),
    path('audit-log/', views.AuditLogView.as_view(), name='admin-audit-log'),
    path('two-factor/', views.TwoFactorStatusView.as_view(), name='admin-two-factor'),
    path('two-factor/setup/', views.TwoFactorSetupView.as_view(), name='admin-two-factor-setup'),
    path('two-factor/confirm/', views.TwoFactorConfirmView.as_view(),
         name='admin-two-factor-confirm'),
    path('two-factor/verify/', views.TwoFactorVerifyView.as_view(),
         name='admin-two-factor-verify'),
    path('two-factor/recovery-codes/', views.TwoFactorRecoveryCodesView.as_view(),
         name='admin-two-factor-recovery-codes'),
]

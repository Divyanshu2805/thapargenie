from django.urls import path

from chat import admin_views as views

urlpatterns = [
    path('stats/', views.StatsView.as_view(), name='admin-stats'),
    path('gaps/', views.GapsView.as_view(), name='admin-gaps'),
    path('feedback/', views.FeedbackListView.as_view(), name='admin-feedback'),
    path('feedback/<uuid:feedback_id>/', views.FeedbackDetailView.as_view(),
         name='admin-feedback-detail'),
    path('settings/', views.SettingsView.as_view(), name='admin-settings'),
]

from django.urls import path

from chat import admin_views as views

urlpatterns = [
    path('stats/', views.StatsView.as_view(), name='admin-stats'),
    path('stats/export/', views.StatsExportView.as_view(), name='admin-stats-export'),
    path('gaps/', views.GapsView.as_view(), name='admin-gaps'),
    path('gaps/export/', views.GapsExportView.as_view(), name='admin-gaps-export'),
    path('complaints/', views.ComplaintsView.as_view(), name='admin-complaints'),
    path('feedback/', views.FeedbackListView.as_view(), name='admin-feedback'),
    path('feedback/export/', views.FeedbackExportView.as_view(), name='admin-feedback-export'),
    path('feedback/<uuid:feedback_id>/', views.FeedbackDetailView.as_view(),
         name='admin-feedback-detail'),
    path('site-feedback/', views.SiteFeedbackListView.as_view(), name='admin-site-feedback'),
    path('site-feedback/<uuid:feedback_id>/', views.SiteFeedbackDetailView.as_view(),
         name='admin-site-feedback-detail'),
    path('settings/', views.SettingsView.as_view(), name='admin-settings'),
    path('playground/', views.PlaygroundView.as_view(), name='admin-playground'),
]

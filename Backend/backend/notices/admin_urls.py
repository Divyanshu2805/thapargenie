from django.urls import path

from notices import admin_views as views

urlpatterns = [
    path('notices/', views.NoticeListView.as_view(), name='admin-notices'),
    path('notices/<uuid:notice_id>/', views.NoticeDetailView.as_view(), name='admin-notice'),
]

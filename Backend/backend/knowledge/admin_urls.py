from django.urls import path

from knowledge import admin_views as views

urlpatterns = [
    path('documents/', views.DocumentListView.as_view(), name='admin-documents'),
    path('documents/url/', views.DocumentFromUrlView.as_view(), name='admin-documents-url'),
    path('documents/text/', views.DocumentFromTextView.as_view(), name='admin-documents-text'),
    path('documents/<uuid:document_id>/', views.DocumentDetailView.as_view(),
         name='admin-document'),
    path('documents/<uuid:document_id>/reprocess/', views.DocumentReprocessView.as_view(),
         name='admin-document-reprocess'),
    path('documents/<uuid:document_id>/enable/', views.DocumentEnableView.as_view(),
         name='admin-document-enable'),
    path('documents/<uuid:document_id>/disable/', views.DocumentDisableView.as_view(),
         name='admin-document-disable'),
    path('documents/<uuid:document_id>/file/', views.DocumentFileView.as_view(),
         name='admin-document-file'),
    path('documents/<uuid:document_id>/chunks/', views.DocumentChunksView.as_view(),
         name='admin-document-chunks'),
    path('chunks/<uuid:chunk_id>/', views.ChunkDetailView.as_view(), name='admin-chunk'),
]

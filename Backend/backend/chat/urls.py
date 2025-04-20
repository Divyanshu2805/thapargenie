from django.urls import path

from chat import views

urlpatterns = [
    path('app-config/', views.AppConfigView.as_view(), name='app-config'),
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path(
        'conversations/<uuid:conversation_id>/',
        views.ConversationDetailView.as_view(),
        name='conversation-detail',
    ),
    path(
        'conversations/<uuid:conversation_id>/messages/',
        views.MessageListView.as_view(),
        name='conversation-messages',
    ),
]

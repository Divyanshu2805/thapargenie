from django.urls import path

from chat import views

urlpatterns = [
    path('app-config/', views.AppConfigView.as_view(), name='app-config'),
    path('coverage/', views.CoverageView.as_view(), name='coverage'),
    path('me/export/', views.ExportView.as_view(), name='me-export'),
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
    path(
        'messages/<uuid:message_id>/regenerate/',
        views.RegenerateView.as_view(),
        name='message-regenerate',
    ),
    path(
        'messages/<uuid:message_id>/suggestions/',
        views.SuggestionsView.as_view(),
        name='message-suggestions',
    ),
    path(
        'messages/<uuid:message_id>/feedback/',
        views.FeedbackView.as_view(),
        name='message-feedback',
    ),
    path(
        'messages/<uuid:message_id>/share/',
        views.ShareView.as_view(),
        name='message-share',
    ),
    path('shared/<str:token>/', views.SharedAnswerView.as_view(), name='shared-answer'),
    path('site-feedback/', views.SiteFeedbackView.as_view(), name='site-feedback'),
    path('sources/<uuid:source_id>/open/', views.SourceOpenView.as_view(), name='source-open'),
]

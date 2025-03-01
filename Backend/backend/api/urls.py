"""Versioned API routes."""

from django.urls import path

from api.views import MeView, RevokeSessionsView

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("me/revoke-sessions/", RevokeSessionsView.as_view(), name="revoke-sessions"),
]

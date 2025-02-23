from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='openapi-schema'),
    path(
        'api/v1/docs/',
        SpectacularSwaggerView.as_view(url_name='openapi-schema'),
        name='api-docs',
    ),
]

if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.append(path('admin/', admin.site.urls))

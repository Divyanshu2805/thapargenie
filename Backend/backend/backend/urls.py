from api import views as api_views
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('', api_views.service_index, name='service-index'),
    path('health/live/', api_views.health_live, name='health-live'),
    path('health/ready/', api_views.health_ready, name='health-ready'),
    path('api/v1/', include('api.urls')),
    path('api/v1/', include('chat.urls')),
    path('api/v1/admin/', include('knowledge.admin_urls')),
    path('api/v1/admin/', include('chat.admin_urls')),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='openapi-schema'),
    path(
        'api/v1/docs/',
        SpectacularSwaggerView.as_view(url_name='openapi-schema'),
        name='api-docs',
    ),
]

if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.append(path('admin/', admin.site.urls))

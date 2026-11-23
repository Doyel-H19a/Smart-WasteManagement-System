"""Root URL configuration for SwachhAI."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import home_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("accounts/", include("accounts.urls")),
    path("wards/", include("waste_management.urls")),
    path("collection/", include("waste_management.collection_urls")),
    path("complaints/", include("complaints.urls")),
    path("notifications/", include("notifications.urls")),
    path("manage/", include("admin_dashboard.urls")),
    path("worker/", include("worker.urls")),
    path("ai/", include("ai_classification.urls")),
]

# Serve uploaded media files only during local development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
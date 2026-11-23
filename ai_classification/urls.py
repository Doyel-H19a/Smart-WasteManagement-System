"""URL routes for the AI classification app."""
from django.urls import path

from . import api, views

app_name = "ai_classification"

urlpatterns = [
    path("classify/", views.classify_view, name="classify"),
    path("classify/<int:pk>/", views.result_view, name="result"),
    path("api/classify/", api.ClassifyAPIView.as_view(), name="api_classify"),
]
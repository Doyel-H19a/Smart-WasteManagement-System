"""URL routes for the complaints app."""
from django.urls import path

from . import views

app_name = "complaints"

urlpatterns = [
    path("", views.complaint_list, name="list"),
    path("new/", views.complaint_create, name="create"),
    path("<int:pk>/", views.complaint_detail, name="detail"),
]
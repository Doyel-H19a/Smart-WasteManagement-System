"""URL routes for the waste_management app."""
from django.urls import path

from . import views

app_name = "waste_management"

urlpatterns = [
    path("", views.ward_list, name="ward_list"),
    path("map/", views.complaint_map, name="map"),
    path("new/", views.ward_create, name="ward_create"),
    path("<int:pk>/edit/", views.ward_update, name="ward_update"),
]
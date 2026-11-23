"""URL routes for the inspections app."""
from django.urls import path

from . import views

app_name = "inspections"

urlpatterns = [
    path("", views.inspection_list, name="list"),
    path("new/", views.inspection_create, name="create"),
    path("<int:pk>/", views.inspection_detail, name="detail"),
    path("<int:pk>/follow-up/", views.follow_up_done, name="follow_up_done"),
]
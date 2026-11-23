"""URL routes for collection schedules and waste movements (mounted at /collection/)."""
from django.urls import path

from . import collection_views as views

app_name = "collection"

urlpatterns = [
    path("schedules/", views.schedule_list, name="schedule_list"),
    path("schedules/new/", views.schedule_create, name="schedule_create"),
    path("schedules/<int:pk>/edit/", views.schedule_update, name="schedule_update"),
    path("schedules/<int:pk>/toggle/", views.schedule_toggle, name="schedule_toggle"),
    path("movements/", views.movement_list, name="movement_list"),
    path("movements/new/", views.movement_create, name="movement_create"),
    path("movements/map/", views.movement_map, name="movement_map"),
]
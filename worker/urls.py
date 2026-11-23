"""URL routes for the worker app."""
from django.urls import path

from . import views

app_name = "worker"

urlpatterns = [
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/accept/", views.task_accept, name="task_accept"),
    path("tasks/<int:pk>/complete/", views.task_complete, name="task_complete"),
]
"""URL routes for the penalties app."""
from django.urls import path

from . import views

app_name = "penalties"

urlpatterns = [
    path("", views.penalty_list, name="list"),
    path("new/", views.penalty_create, name="create"),
    path("<int:pk>/", views.penalty_detail, name="detail"),
    path("<int:pk>/dispute/", views.penalty_dispute, name="dispute"),
    path("<int:pk>/pay/", views.penalty_pay, name="pay"),
    path("<int:pk>/reject-dispute/", views.penalty_reject_dispute, name="reject_dispute"),
    path("<int:pk>/waive/", views.penalty_waive, name="waive"),
    path("<int:pk>/cancel/", views.penalty_cancel, name="cancel"),
]
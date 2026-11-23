"""URL routes for the Municipal Admin review console."""
from django.urls import path

from . import views

app_name = "admin_dashboard"

urlpatterns = [
    path("complaints/", views.complaint_queue, name="queue"),
    path("complaints/<int:pk>/", views.complaint_detail, name="complaint_detail"),
    path("complaints/<int:pk>/review/", views.complaint_start_review, name="start_review"),
    path("complaints/<int:pk>/reject/", views.complaint_reject, name="reject"),
    path("complaints/<int:pk>/assign/", views.complaint_assign, name="assign"),
    path("complaints/<int:pk>/verify/", views.complaint_verify, name="verify"),
    path("complaints/<int:pk>/rework/", views.complaint_rework, name="rework"),
    path("workers/", views.worker_overview, name="workers"),
]
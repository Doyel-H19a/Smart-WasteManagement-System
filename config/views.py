"""Project-level views (public landing page)."""
from django.shortcuts import render

from accounts.models import User
from accounts.navigation import ROLE_DESCRIPTIONS, ROLE_ICONS

PLATFORM_FEATURES = [
    {"icon": "bi-megaphone", "title": "Complaint Reporting",
     "text": "Citizens report waste problems with photos and location details."},
    {"icon": "bi-cpu", "title": "AI Waste Classification",
     "text": "An interface prepared for a future CNN model. Demonstration mode is clearly labelled until a trained model is added."},
    {"icon": "bi-truck", "title": "Collection & Task Assignment",
     "text": "Schedule collections and assign field workers to complaints."},
    {"icon": "bi-geo-alt", "title": "Maps & Waste Movement",
     "text": "Leaflet and OpenStreetMap views of complaints, wards and routes."},
    {"icon": "bi-clipboard2-pulse", "title": "Health & Sanitation Inspections",
     "text": "Inspection records, findings and follow-up actions."},
    {"icon": "bi-mortarboard", "title": "Training & Quizzes",
     "text": "Awareness content and quizzes for citizens, workers and champions."},
    {"icon": "bi-award", "title": "Rewards & Penalties",
     "text": "Incentives for good practice and penalties for violations."},
    {"icon": "bi-bar-chart-line", "title": "Analytics & Reports",
     "text": "Interactive Chart.js dashboards for city-level decisions."},
]

WORKFLOW_STEPS = [
    {"title": "Report", "text": "A citizen submits a waste complaint."},
    {"title": "Review", "text": "The Municipal Admin reviews it."},
    {"title": "Assign", "text": "A waste worker is assigned."},
    {"title": "Accept", "text": "The worker accepts the task."},
    {"title": "Resolve", "text": "The worker completes it and uploads proof."},
    {"title": "Verify", "text": "The admin verifies and the citizen is notified."},
]


def home_view(request):
    """Public landing page."""
    roles = [
        {
            "label": label,
            "icon": ROLE_ICONS.get(value, "bi-person"),
            "text": ROLE_DESCRIPTIONS.get(value, ""),
        }
        for value, label in User.Role.choices
    ]
    context = {
        "features": PLATFORM_FEATURES,
        "roles": roles,
        "workflow_steps": WORKFLOW_STEPS,
    }
    return render(request, "home.html", context)
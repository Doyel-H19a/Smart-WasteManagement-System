"""Role metadata and sidebar menus for SwachhAI."""

ROLE_ICONS = {
    "citizen": "bi-person-heart",
    "worker": "bi-truck",
    "municipal_admin": "bi-building",
    "health_officer": "bi-heart-pulse",
    "executive_officer": "bi-briefcase",
    "super_admin": "bi-shield-lock",
    "green_champion": "bi-tree",
    "bulk_generator": "bi-box-seam",
}

ROLE_DESCRIPTIONS = {
    "citizen": "Report waste problems, track complaints, learn and earn rewards.",
    "worker": "Receive assigned tasks, collect waste and upload proof of completion.",
    "municipal_admin": "Review complaints, assign workers and manage wards and schedules.",
    "health_officer": "Conduct sanitation inspections and monitor public health compliance.",
    "executive_officer": "Oversee city-wide performance with analytics and reports.",
    "super_admin": "Manage users, roles, permissions and system configuration.",
    "green_champion": "Lead community monitoring and awareness in your neighbourhood.",
    "bulk_generator": "Manage bulk waste pickups, records and compliance.",
}

# Shown to every authenticated user: (label, bootstrap icon, URL name)
COMMON_MENU = [
    ("Dashboard", "bi-speedometer2", "accounts:dashboard"),
    ("My Profile", "bi-person-circle", "accounts:profile"),
]

# Modules planned for later phases: (label, bootstrap icon)
ROLE_MODULES = {
    "citizen": [
        ("Report Complaint", "bi-megaphone"),
        ("My Complaints", "bi-list-check"),
        ("Training & Quizzes", "bi-mortarboard"),
        ("Rewards", "bi-award"),
        ("Marketplace", "bi-shop"),
        ("Notifications", "bi-bell"),
    ],
    "worker": [
        ("My Tasks", "bi-clipboard-check"),
        ("Collection Schedule", "bi-calendar-event"),
        ("Waste Movement", "bi-signpost-split"),
        ("Notifications", "bi-bell"),
    ],
    "municipal_admin": [
        ("Review Complaints", "bi-inbox"),
        ("Assign Workers", "bi-people"),
        ("Ward Management", "bi-map"),
        ("Collection Scheduling", "bi-calendar-event"),
        ("Penalties", "bi-exclamation-octagon"),
        ("Analytics", "bi-bar-chart-line"),
    ],
    "health_officer": [
        ("Inspections", "bi-clipboard2-pulse"),
        ("Sanitation Reports", "bi-file-earmark-text"),
        ("Penalties", "bi-exclamation-octagon"),
        ("Analytics", "bi-bar-chart-line"),
    ],
    "executive_officer": [
        ("City Analytics", "bi-graph-up"),
        ("Reports", "bi-file-earmark-bar-graph"),
        ("Ward Performance", "bi-map"),
    ],
    "super_admin": [
        ("User Management", "bi-people"),
        ("System Settings", "bi-gear"),
        ("Reports", "bi-file-earmark-bar-graph"),
    ],
    "green_champion": [
        ("Community Monitoring", "bi-binoculars"),
        ("Training & Quizzes", "bi-mortarboard"),
        ("Rewards", "bi-award"),
    ],
    "bulk_generator": [
        ("Bulk Pickups", "bi-box-seam"),
        ("Waste Records", "bi-journal-text"),
        ("Compliance", "bi-patch-check"),
        ("Penalties", "bi-exclamation-octagon"),
    ],
}


def get_menu_for_role(role):
    """Return the sidebar entries (label, icon, url_name or None) for a role."""
    planned = [(label, icon, None) for label, icon in ROLE_MODULES.get(role, [])]
    return COMMON_MENU + planned
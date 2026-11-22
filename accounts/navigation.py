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

# Menu entries are (label, bootstrap icon, URL name). A URL name of None means
# the module is planned for a later phase and is shown as "Coming soon".
MENU_TOP = [
    ("Dashboard", "bi-speedometer2", "accounts:dashboard"),
]

MENU_BOTTOM = [
    ("Notifications", "bi-bell", "notifications:list"),
    ("My Profile", "bi-person-circle", "accounts:profile"),
]

ROLE_MODULES = {
    "citizen": [
        ("Report Complaint", "bi-megaphone", "complaints:create"),
        ("My Complaints", "bi-list-check", "complaints:list"),
        ("Training & Quizzes", "bi-mortarboard", None),
        ("Rewards", "bi-award", None),
        ("Marketplace", "bi-shop", None),
    ],
    "worker": [
        ("My Tasks", "bi-clipboard-check", None),
        ("Collection Schedule", "bi-calendar-event", None),
        ("Waste Movement", "bi-signpost-split", None),
    ],
    "municipal_admin": [
        ("Review Complaints", "bi-inbox", None),
        ("Assign Workers", "bi-people", None),
        ("Ward Management", "bi-map", "waste_management:ward_list"),
        ("Collection Scheduling", "bi-calendar-event", None),
        ("Penalties", "bi-exclamation-octagon", None),
        ("Analytics", "bi-bar-chart-line", None),
    ],
    "health_officer": [
        ("Inspections", "bi-clipboard2-pulse", None),
        ("Sanitation Reports", "bi-file-earmark-text", None),
        ("Penalties", "bi-exclamation-octagon", None),
        ("Analytics", "bi-bar-chart-line", None),
    ],
    "executive_officer": [
        ("City Analytics", "bi-graph-up", None),
        ("Reports", "bi-file-earmark-bar-graph", None),
        ("Ward Performance", "bi-map", None),
    ],
    "super_admin": [
        ("User Management", "bi-people", None),
        ("Ward Management", "bi-map", "waste_management:ward_list"),
        ("System Settings", "bi-gear", None),
        ("Reports", "bi-file-earmark-bar-graph", None),
    ],
    "green_champion": [
        ("Community Monitoring", "bi-binoculars", None),
        ("Training & Quizzes", "bi-mortarboard", None),
        ("Rewards", "bi-award", None),
    ],
    "bulk_generator": [
        ("Bulk Pickups", "bi-box-seam", None),
        ("Waste Records", "bi-journal-text", None),
        ("Compliance", "bi-patch-check", None),
        ("Penalties", "bi-exclamation-octagon", None),
    ],
}


def get_menu_for_role(role):
    """Return the sidebar entries (label, icon, url_name or None) for a role."""
    return MENU_TOP + list(ROLE_MODULES.get(role, [])) + MENU_BOTTOM
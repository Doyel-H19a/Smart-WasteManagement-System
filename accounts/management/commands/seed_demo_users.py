"""Create demo users for all eight SwachhAI roles (development only)."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

DEMO_PASSWORD = "Demo@12345"  # demo data only, never use in production

DEMO_USERS = [
    {"username": "citizen_demo", "first_name": "Anita", "last_name": "Das",
     "email": "citizen@swachhai.local", "role": User.Role.CITIZEN,
     "phone_number": "9830000001", "address": "12 Gariahat Road, Kolkata 700019"},
    {"username": "worker_demo", "first_name": "Ravi", "last_name": "Kumar",
     "email": "worker@swachhai.local", "role": User.Role.WORKER,
     "phone_number": "9830000002", "address": "Ward 45 Depot, Tollygunge, Kolkata"},
    {"username": "admin_demo", "first_name": "Meera", "last_name": "Sen",
     "email": "municipal@swachhai.local", "role": User.Role.MUNICIPAL_ADMIN,
     "phone_number": "9830000003", "address": "Municipal Office, Salt Lake, Kolkata"},
    {"username": "health_demo", "first_name": "Arjun", "last_name": "Roy",
     "email": "health@swachhai.local", "role": User.Role.HEALTH_OFFICER,
     "phone_number": "9830000004", "address": "Health Dept, Park Street, Kolkata"},
    {"username": "executive_demo", "first_name": "Sunita", "last_name": "Ghosh",
     "email": "executive@swachhai.local", "role": User.Role.EXECUTIVE_OFFICER,
     "phone_number": "9830000005", "address": "Civic Centre, Kolkata"},
    {"username": "superadmin_demo", "first_name": "Debashis", "last_name": "Banerjee",
     "email": "superadmin@swachhai.local", "role": User.Role.SUPER_ADMIN,
     "phone_number": "9830000006", "address": "IT Cell, Civic Centre, Kolkata",
     "is_staff": True, "is_superuser": True},
    {"username": "champion_demo", "first_name": "Priya", "last_name": "Mukherjee",
     "email": "champion@swachhai.local", "role": User.Role.GREEN_CHAMPION,
     "phone_number": "9830000007", "address": "45 Lake Gardens, Kolkata 700045"},
    {"username": "bulk_demo", "first_name": "Kolkata Grand", "last_name": "Hotel",
     "email": "bulk@swachhai.local", "role": User.Role.BULK_GENERATOR,
     "phone_number": "9830000008", "address": "Camac Street, Kolkata 700016"},
]


class Command(BaseCommand):
    help = "Create (or reset) demo users for all eight roles. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo users can only be created when DEBUG=True.")

        for data in DEMO_USERS:
            fields = dict(data)
            username = fields.pop("username")
            user, created = User.objects.update_or_create(username=username, defaults=fields)
            user.set_password(DEMO_PASSWORD)
            user.save()
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action}: {username} ({user.get_role_display()})")

        self.stdout.write(self.style.SUCCESS(f"Done. Demo password for all users: {DEMO_PASSWORD}"))
"""Move demo complaints through the real workflow (development only)."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from complaints import services
from complaints.models import Complaint

# (complaint title, should the worker also accept it?)
DEMO_STEPS = [
    ("Missed door-to-door collection", False),
    ("Garbage heap near Gariahat market", True),
]


class Command(BaseCommand):
    help = "Assign demo complaints to worker_demo using the real workflow. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo workflow data can only be created when DEBUG=True.")

        try:
            admin = User.objects.get(username="admin_demo")
            worker = User.objects.get(username="worker_demo")
        except User.DoesNotExist:
            raise CommandError("Run `python manage.py seed_demo_users` first.")

        for title, accept in DEMO_STEPS:
            complaint = Complaint.objects.filter(
                citizen__username="citizen_demo", title=title
            ).first()
            if complaint is None:
                self.stdout.write(f"Skipped (not found): {title}")
                continue
            if complaint.status != Complaint.Status.SUBMITTED:
                self.stdout.write(f"Skipped (already in progress): {complaint}")
                continue

            complaint = services.start_review(complaint, admin)
            complaint = services.assign_worker(
                complaint, admin, worker, complaint.priority,
                "Demo task: please collect the waste and upload a proof photo.",
            )
            if accept:
                complaint = services.accept_assignment(complaint, worker)
            self.stdout.write(f"Moved: {complaint} -> {complaint.get_status_display()}")

        self.stdout.write(self.style.SUCCESS("Done. Log in as worker_demo to see the tasks."))
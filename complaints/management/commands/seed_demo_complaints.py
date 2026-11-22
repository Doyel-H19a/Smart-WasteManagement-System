"""Create demo complaints for the demo citizen (development only)."""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from complaints.models import Complaint, ComplaintStatusHistory
from notifications.models import Notification
from notifications.services import notify
from waste_management.models import Ward

S = Complaint.Status
C = Complaint.Category
P = Complaint.Priority

DEMO_COMPLAINTS = [
    {"title": "Garbage heap near Gariahat market", "category": C.ILLEGAL_DUMPING, "ward_number": 1,
     "status": S.SUBMITTED, "priority": P.MEDIUM,
     "address": "Opposite Gariahat Market, Kolkata 700019",
     "description": "A large pile of mixed garbage has been growing beside the market gate for a week.",
     "latitude": Decimal("22.518000"), "longitude": Decimal("88.365000"), "note": ""},
    {"title": "Overflowing community bin", "category": C.OVERFLOWING_BIN, "ward_number": 5,
     "status": S.UNDER_REVIEW, "priority": P.HIGH,
     "address": "Lake Gardens, near the community park",
     "description": "The community bin has not been emptied for four days and waste is spilling onto the road.",
     "latitude": None, "longitude": None, "note": "Complaint is being reviewed by the municipal office."},
    {"title": "Missed door-to-door collection", "category": C.MISSED_COLLECTION, "ward_number": 1,
     "status": S.SUBMITTED, "priority": P.LOW,
     "address": "12 Gariahat Road, Kolkata 700019",
     "description": "The collection vehicle did not visit our lane on Monday or Tuesday.",
     "latitude": None, "longitude": None, "note": ""},
    {"title": "Construction debris blocking footpath", "category": C.CONSTRUCTION_DEBRIS, "ward_number": 2,
     "status": S.RESOLVED, "priority": P.MEDIUM,
     "address": "Tollygunge Circular Road",
     "description": "Bricks and rubble were dumped on the footpath, forcing pedestrians onto the road.",
     "latitude": None, "longitude": None, "note": "Sample data: marked as resolved."},
    {"title": "Duplicate report of the same heap", "category": C.OTHER, "ward_number": 1,
     "status": S.REJECTED, "priority": P.LOW,
     "address": "Opposite Gariahat Market, Kolkata 700019",
     "description": "Second report about the heap near the market, submitted by mistake.",
     "latitude": None, "longitude": None, "note": "Duplicate of an earlier complaint."},
]


class Command(BaseCommand):
    help = "Create demo complaints for citizen_demo. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo complaints can only be created when DEBUG=True.")

        try:
            citizen = User.objects.get(username="citizen_demo")
        except User.DoesNotExist:
            raise CommandError("Run `python manage.py seed_demo_users` first.")

        created_count = 0
        for item in DEMO_COMPLAINTS:
            data = dict(item)
            title = data.pop("title")
            note = data.pop("note")
            ward_number = data.pop("ward_number")
            try:
                ward = Ward.objects.get(ward_number=ward_number)
            except Ward.DoesNotExist:
                raise CommandError("Run `python manage.py seed_demo_wards` first.")

            complaint, created = Complaint.objects.get_or_create(
                citizen=citizen, title=title, defaults={**data, "ward": ward}
            )
            if not created:
                self.stdout.write(f"Exists:  {complaint}")
                continue

            created_count += 1
            ComplaintStatusHistory.objects.create(
                complaint=complaint, status=S.SUBMITTED,
                changed_by=citizen, note="Complaint submitted by citizen.",
            )
            if complaint.status != S.SUBMITTED:
                ComplaintStatusHistory.objects.create(
                    complaint=complaint, status=complaint.status, note=note
                )
            notify(
                citizen,
                title=f"Complaint {complaint.reference}: {complaint.get_status_display()}",
                message=complaint.title,
                category=Notification.Category.COMPLAINT,
                link=complaint.get_absolute_url(),
            )
            self.stdout.write(f"Created: {complaint}")

        self.stdout.write(self.style.SUCCESS(f"Done. {created_count} new demo complaint(s)."))
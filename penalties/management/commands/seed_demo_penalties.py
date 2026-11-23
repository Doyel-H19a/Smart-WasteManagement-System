"""Create demo penalties (development only)."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from inspections.models import Inspection
from penalties import services
from penalties.models import Penalty, PenaltyEvent
from waste_management.models import Ward

Status = Penalty.Status
V = Penalty.Violation

BULK_DESCRIPTION = "Wet and dry waste mixed in the bulk containers (demo)."

# (ward number, violation, description, amount, due offset in days, status)
DEMO_CITIZEN_PENALTIES = [
    (1, V.ILLEGAL_DUMPING, "Garbage dumped beside the market gate (demo).", "500.00", -5, Status.ISSUED),
    (2, V.NO_SEGREGATION, "Mixed waste handed to the collection vehicle (demo).", "1000.00", -20, Status.PAID),
    (5, V.OPEN_BURNING, "Waste burnt in an open plot (demo).", "750.00", 5, Status.DISPUTED),
]


class Command(BaseCommand):
    help = "Create demo penalties. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo penalties can only be created when DEBUG=True.")

        try:
            officer = User.objects.get(username="health_demo")
            admin = User.objects.get(username="admin_demo")
            citizen = User.objects.get(username="citizen_demo")
            bulk = User.objects.get(username="bulk_demo")
        except User.DoesNotExist:
            raise CommandError("Run `python manage.py seed_demo_users` first.")

        wards = {w.ward_number: w for w in Ward.objects.all()}
        if not wards:
            raise CommandError("Run `python manage.py seed_demo_wards` first.")

        today = timezone.localdate()
        now = timezone.now()
        created_count = 0

        # 1. Through the real service (sends a notification to the generator).
        ward6 = wards.get(6)
        if ward6 is None:
            self.stdout.write("Skipped (ward 6 missing): bulk generator penalty")
        elif Penalty.objects.filter(issued_to=bulk, description=BULK_DESCRIPTION).exists():
            self.stdout.write(f"Exists:  {BULK_DESCRIPTION}")
        else:
            inspection = Inspection.objects.filter(bulk_generator=bulk, ward=ward6).first()
            penalty = Penalty(
                issued_to=bulk, ward=ward6, inspection=inspection,
                violation_type=V.BULK_NON_COMPLIANCE, description=BULK_DESCRIPTION,
                amount=Decimal("5000.00"), due_date=today + timedelta(days=14),
            )
            services.issue_penalty(penalty, officer)
            created_count += 1
            self.stdout.write(f"Created: {penalty}")

        # 2. Written directly so past due dates and later statuses can be shown.
        for number, violation, description, amount, due_offset, status in DEMO_CITIZEN_PENALTIES:
            ward = wards.get(number)
            if ward is None:
                self.stdout.write(f"Skipped (ward {number} missing): {description}")
                continue
            if Penalty.objects.filter(issued_to=citizen, description=description).exists():
                self.stdout.write(f"Exists:  {description}")
                continue

            penalty = Penalty.objects.create(
                issued_to=citizen, issued_by=officer, ward=ward, violation_type=violation,
                description=description, amount=Decimal(amount),
                due_date=today + timedelta(days=due_offset), status=Status.ISSUED,
            )
            PenaltyEvent.objects.create(
                penalty=penalty, status=Status.ISSUED, actor=officer, note="Penalty issued (demo data)."
            )
            if status == Status.PAID:
                penalty.status = Status.PAID
                penalty.paid_at = now - timedelta(days=2)
                penalty.payment_reference = "RCPT-DEMO-001"
                penalty.recorded_by = admin
                penalty.save()
                PenaltyEvent.objects.create(
                    penalty=penalty, status=Status.PAID, actor=admin,
                    note="Payment recorded. Reference: RCPT-DEMO-001 (demo data).",
                )
            elif status == Status.DISPUTED:
                penalty.status = Status.DISPUTED
                penalty.dispute_reason = "I was not in the city on that date (demo data)."
                penalty.disputed_at = now - timedelta(days=1)
                penalty.save()
                PenaltyEvent.objects.create(
                    penalty=penalty, status=Status.DISPUTED, actor=citizen,
                    note="Disputed: I was not in the city on that date (demo data).",
                )
            created_count += 1
            self.stdout.write(f"Created: {penalty}")

        self.stdout.write(self.style.SUCCESS(f"Done. {created_count} demo penalty(ies) created."))
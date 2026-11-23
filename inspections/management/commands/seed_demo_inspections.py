"""Create demo inspections for the demo Health Officer (development only)."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from inspections import services
from inspections.models import Inspection
from waste_management.models import Ward

C = Inspection.Category
O = Inspection.Outcome

# (ward, category, place, address, uses bulk_demo?, days ago, (segregation, cleanliness, bins),
#  outcome, findings, recommendations, follow-up in N days or None)
DEMO_INSPECTIONS = [
    (1, C.COLLECTION_POINT, "Gariahat market collection point (demo)",
     "Opposite Gariahat Market, Kolkata", False, 2, (3, 2, 3), O.MINOR,
     "Bins were overflowing and loose waste lay around them. Segregation was poor.",
     "Increase collection frequency and add a second bin.", 7),
    (6, C.BULK_PREMISES, "Kolkata Grand Hotel kitchen and bin yard (demo)",
     "Camac Street, Kolkata 700016", True, 3, (2, 3, 2), O.MAJOR,
     "Wet and dry waste were mixed in the bulk containers and the yard drain was partly blocked.",
     "Separate wet and dry waste at source and clear the drain within a week.", 7),
    (5, C.PUBLIC_AREA, "Lake Gardens park lane (demo)",
     "Lake Gardens, Kolkata 700045", False, 5, (5, 4, 5), O.COMPLIANT,
     "The lane was clean and the bins were in good condition.", "", None),
    (2, C.FACILITY, "Tollygunge transfer point (demo)",
     "Tollygunge Circular Road, Kolkata", False, 6, (4, 4, 3), O.COMPLIANT,
     "Waste was handled in an orderly way. One bin lid was damaged.",
     "Replace the damaged bin lid.", None),
]


class Command(BaseCommand):
    help = "Create demo inspections for health_demo. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo inspections can only be created when DEBUG=True.")

        try:
            officer = User.objects.get(username="health_demo")
            bulk = User.objects.get(username="bulk_demo")
        except User.DoesNotExist:
            raise CommandError("Run `python manage.py seed_demo_users` first.")

        wards = {w.ward_number: w for w in Ward.objects.all()}
        if not wards:
            raise CommandError("Run `python manage.py seed_demo_wards` first.")

        today = timezone.localdate()
        created_count = 0
        for (number, category, place, address, use_bulk, days_ago, ratings, outcome,
             findings, recommendations, follow_up_days) in DEMO_INSPECTIONS:
            ward = wards.get(number)
            if ward is None:
                self.stdout.write(f"Skipped (ward {number} missing): {place}")
                continue
            if Inspection.objects.filter(inspector=officer, premises_name=place).exists():
                self.stdout.write(f"Exists:  {place}")
                continue

            inspection = Inspection(
                ward=ward, category=category, premises_name=place, address=address,
                bulk_generator=bulk if use_bulk else None,
                inspection_date=today - timedelta(days=days_ago),
                segregation_rating=ratings[0], cleanliness_rating=ratings[1],
                bin_condition_rating=ratings[2], outcome=outcome,
                findings=findings, recommendations=recommendations,
                follow_up_required=follow_up_days is not None,
                follow_up_date=today + timedelta(days=follow_up_days) if follow_up_days else None,
            )
            services.record_inspection(inspection, officer)
            created_count += 1
            self.stdout.write(f"Created: {inspection}")

        self.stdout.write(self.style.SUCCESS(f"Done. {created_count} demo inspection(s) created."))
"""Create demo collection schedules and waste movements (development only)."""
from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from waste_management.models import CollectionSchedule, Ward, WasteMovement

VEHICLE = "WB-DEMO-01"

# (ward number, route, waste type, weekday, start, end, assigned to worker_demo?, active?)
DEMO_SCHEDULES = [
    (1, "Gariahat main road", "wet", 0, time(6, 0), time(9, 0), True, True),
    (1, "Gariahat main road", "dry", 3, time(6, 0), time(9, 0), True, True),
    (2, "Tollygunge circular road", "mixed", 1, time(7, 0), time(10, 0), True, True),
    (3, "Salt Lake sector lanes", "wet", 2, time(6, 30), time(9, 30), False, True),
    (4, "Park Street area", "hazardous", 4, time(10, 0), time(12, 0), False, True),
    (5, "Lake Gardens blocks", "wet", 5, time(6, 0), time(8, 30), True, True),
    (7, "Behala main market", "e_waste", 6, time(9, 0), time(11, 0), False, False),
]

# (ward number, type, waste, kg, from, to, days ago, hours ago, lat/lng offset index)
DEMO_MOVEMENTS = [
    (1, "pickup", "wet", "420.50", "Gariahat market collection point", f"Collection vehicle {VEHICLE}", 1, 2, 1),
    (1, "pickup", "dry", "180.00", "Gariahat main road bins", f"Collection vehicle {VEHICLE}", 2, 3, 2),
    (1, "transfer", "wet", "1250.00", "Gariahat compactor point", "Central transfer station (demo)", 1, 0, 3),
    (2, "disposal", "wet", "3800.00", "Central transfer station (demo)", "Processing plant (demo)", 3, 1, 4),
    (2, "pickup", "mixed", "310.25", "Tollygunge circular road bins", f"Collection vehicle {VEHICLE}", 0, 5, 5),
    (5, "pickup", "hazardous", "45.00", "Lake Gardens clinic bins", f"Collection vehicle {VEHICLE}", 4, 2, 6),
]


class Command(BaseCommand):
    help = "Create demo collection schedules and waste movements. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo collection data can only be created when DEBUG=True.")

        try:
            worker = User.objects.get(username="worker_demo")
            admin = User.objects.get(username="admin_demo")
        except User.DoesNotExist:
            raise CommandError("Run `python manage.py seed_demo_users` first.")

        wards = {w.ward_number: w for w in Ward.objects.all()}
        if not wards:
            raise CommandError("Run `python manage.py seed_demo_wards` first.")

        schedules_created = 0
        for number, route, waste, weekday, start, end, assigned, active in DEMO_SCHEDULES:
            ward = wards.get(number)
            if ward is None:
                self.stdout.write(f"Skipped (ward {number} missing): {route}")
                continue
            schedule, created = CollectionSchedule.objects.get_or_create(
                ward=ward, route_name=route, waste_type=waste, weekday=weekday, start_time=start,
                defaults={
                    "end_time": end,
                    "assigned_worker": worker if assigned else None,
                    "vehicle_number": VEHICLE if assigned else "",
                    "is_active": active,
                    "notes": "Demo schedule.",
                    "created_by": admin,
                },
            )
            schedules_created += int(created)
            self.stdout.write(f"{'Created' if created else 'Exists '}: {schedule}")

        movements_created = 0
        now = timezone.now()
        for number, mtype, waste, kg, origin, destination, days, hours, offset in DEMO_MOVEMENTS:
            ward = wards.get(number)
            if ward is None:
                continue
            latitude = longitude = None
            if ward.latitude is not None and ward.longitude is not None:
                # Small repeatable offset (about 300 m) so markers do not overlap.
                latitude = (ward.latitude + Decimal(offset * 7 % 11 - 5) / Decimal(5000)).quantize(Decimal("0.000001"))
                longitude = (ward.longitude + Decimal(offset * 5 % 11 - 5) / Decimal(5000)).quantize(Decimal("0.000001"))
            movement, created = WasteMovement.objects.get_or_create(
                logged_by=worker, ward=ward, movement_type=mtype, waste_type=waste,
                quantity_kg=Decimal(kg), from_location=origin, to_location=destination,
                defaults={
                    "vehicle_number": VEHICLE,
                    "latitude": latitude,
                    "longitude": longitude,
                    "notes": "Demo entry.",
                    "moved_at": now - timedelta(days=days, hours=hours),
                },
            )
            movements_created += int(created)
            self.stdout.write(f"{'Created' if created else 'Exists '}: {movement}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. {schedules_created} schedule(s) and {movements_created} movement(s) created."
        ))
"""Create demo wards (development only)."""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from waste_management.models import Ward

DEMO_WARDS = [
    {"ward_number": 1, "name": "Gariahat", "zone": "South", "population": 42000,
     "latitude": Decimal("22.518000"), "longitude": Decimal("88.365000")},
    {"ward_number": 2, "name": "Tollygunge", "zone": "South", "population": 51000,
     "latitude": Decimal("22.498500"), "longitude": Decimal("88.347000")},
    {"ward_number": 3, "name": "Salt Lake", "zone": "East", "population": 38000,
     "latitude": Decimal("22.580000"), "longitude": Decimal("88.418000")},
    {"ward_number": 4, "name": "Park Street", "zone": "Central", "population": 29000,
     "latitude": Decimal("22.553500"), "longitude": Decimal("88.351500")},
    {"ward_number": 5, "name": "Lake Gardens", "zone": "South", "population": 33000,
     "latitude": Decimal("22.505000"), "longitude": Decimal("88.364000")},
    {"ward_number": 6, "name": "Camac Street", "zone": "Central", "population": 25000,
     "latitude": Decimal("22.547000"), "longitude": Decimal("88.351000")},
    {"ward_number": 7, "name": "Behala", "zone": "South-West", "population": 60000,
     "latitude": Decimal("22.498000"), "longitude": Decimal("88.318000")},
    {"ward_number": 8, "name": "Dum Dum", "zone": "North", "population": 47000,
     "latitude": Decimal("22.623000"), "longitude": Decimal("88.390000")},
]


class Command(BaseCommand):
    help = "Create (or update) demo wards. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo wards can only be created when DEBUG=True.")

        for data in DEMO_WARDS:
            fields = dict(data)
            number = fields.pop("ward_number")
            ward, created = Ward.objects.update_or_create(ward_number=number, defaults=fields)
            self.stdout.write(f"{'Created' if created else 'Updated'}: {ward}")

        self.stdout.write(self.style.SUCCESS(f"Done. {len(DEMO_WARDS)} demo wards ready."))
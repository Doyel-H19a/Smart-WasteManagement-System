"""Give demo complaints map coordinates near their ward centre (development only)."""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from complaints.models import Complaint


class Command(BaseCommand):
    help = "Add demo coordinates to complaints that have none. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo locations can only be added when DEBUG=True.")

        updated = 0
        queryset = Complaint.objects.filter(latitude__isnull=True, longitude__isnull=True).select_related("ward")
        for complaint in queryset:
            ward = complaint.ward
            if ward.latitude is None or ward.longitude is None:
                continue
            # A small, repeatable offset (about +/- 500 m) so markers do not overlap.
            lat_offset = Decimal((complaint.pk * 37) % 100 - 50) / Decimal(10000)
            lng_offset = Decimal((complaint.pk * 53) % 100 - 50) / Decimal(10000)
            complaint.latitude = (ward.latitude + lat_offset).quantize(Decimal("0.000001"))
            complaint.longitude = (ward.longitude + lng_offset).quantize(Decimal("0.000001"))
            complaint.save(update_fields=["latitude", "longitude", "updated_at"])
            updated += 1
            self.stdout.write(f"Located: {complaint}")

        self.stdout.write(self.style.SUCCESS(f"Done. {updated} complaint(s) given demo coordinates."))
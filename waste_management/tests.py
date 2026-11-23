"""Automated tests for ward management and the complaint map."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from complaints.models import Complaint

from .models import Ward

PASSWORD = "StrongPass#2026"


class WardManagementTests(TestCase):
    def setUp(self):
        User.objects.create_user("ward_admin", "wa@example.com", PASSWORD, role=User.Role.MUNICIPAL_ADMIN)
        User.objects.create_user("ward_citizen", "wc@example.com", PASSWORD, role=User.Role.CITIZEN)

    def test_municipal_admin_can_create_ward(self):
        self.client.login(username="ward_admin", password=PASSWORD)
        response = self.client.post(
            reverse("waste_management:ward_create"),
            {"ward_number": 10, "name": "New Ward", "zone": "North", "is_active": "on"},
        )
        self.assertRedirects(response, reverse("waste_management:ward_list"))
        self.assertTrue(Ward.objects.filter(ward_number=10, name="New Ward").exists())

    def test_citizen_cannot_access_ward_pages(self):
        self.client.login(username="ward_citizen", password=PASSWORD)
        response = self.client.get(reverse("waste_management:ward_list"))
        self.assertEqual(response.status_code, 403)

    def test_duplicate_ward_number_is_rejected(self):
        Ward.objects.create(ward_number=10, name="Existing")
        self.client.login(username="ward_admin", password=PASSWORD)
        response = self.client.post(
            reverse("waste_management:ward_create"),
            {"ward_number": 10, "name": "Duplicate", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Ward.objects.count(), 1)


class ComplaintMapTests(TestCase):
    def setUp(self):
        self.ward = Ward.objects.create(
            ward_number=1, name="Map Ward", latitude=Decimal("22.518000"), longitude=Decimal("88.365000")
        )
        self.citizen = User.objects.create_user("mc1", "mc1@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.other = User.objects.create_user("mc2", "mc2@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.admin = User.objects.create_user("ma1", "ma1@example.com", PASSWORD, role=User.Role.MUNICIPAL_ADMIN)
        self.worker = User.objects.create_user("mw1", "mw1@example.com", PASSWORD, role=User.Role.WORKER)
        self.champion = User.objects.create_user("mg1", "mg1@example.com", PASSWORD, role=User.Role.GREEN_CHAMPION)

        self.make(self.citizen, "Mine", located=True)
        self.make(self.citizen, "Mine without coordinates", located=False)
        self.make(self.other, "Someone else's", located=True)
        self.make(self.other, "Assigned to worker", located=True, assigned_worker=self.worker)

    def make(self, citizen, title, located, **extra):
        coords = {"latitude": Decimal("22.520000"), "longitude": Decimal("88.360000")} if located else {}
        return Complaint.objects.create(
            citizen=citizen, ward=self.ward, title=title, category=Complaint.Category.OTHER,
            description="A description that is long enough.", address="Test street", **coords, **extra,
        )

    def get_map(self, username):
        self.client.login(username=username, password=PASSWORD)
        return self.client.get(reverse("waste_management:map"))

    def test_citizen_sees_only_own_located_complaints(self):
        response = self.get_map("mc1")
        titles = [c["title"] for c in response.context["map_data"]["complaints"]]
        self.assertEqual(titles, ["Mine"])
        self.assertEqual(response.context["missing_count"], 1)
        self.assertEqual(response.context["map_data"]["wards"], [])

    def test_admin_sees_all_located_complaints_and_wards(self):
        response = self.get_map("ma1")
        self.assertEqual(len(response.context["map_data"]["complaints"]), 3)
        self.assertEqual(len(response.context["map_data"]["wards"]), 1)

    def test_worker_sees_only_assigned_complaints(self):
        response = self.get_map("mw1")
        titles = [c["title"] for c in response.context["map_data"]["complaints"]]
        self.assertEqual(titles, ["Assigned to worker"])

    def test_role_without_map_gets_403(self):
        self.assertEqual(self.get_map("mg1").status_code, 403)

    def test_map_requires_login(self):
        response = self.client.get(reverse("waste_management:map"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
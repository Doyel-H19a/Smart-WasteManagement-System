"""Automated tests for ward management."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

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
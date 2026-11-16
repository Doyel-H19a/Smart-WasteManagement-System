"""Automated tests for the accounts app."""
from django.test import TestCase
from django.urls import reverse

from .models import User

VALID_PASSWORD = "StrongPass#2026"


def registration_data(**overrides):
    data = {
        "first_name": "Test",
        "last_name": "User",
        "username": "testcitizen",
        "email": "test@example.com",
        "phone_number": "9876543210",
        "role": "citizen",
        "password1": VALID_PASSWORD,
        "password2": VALID_PASSWORD,
    }
    data.update(overrides)
    return data


class RegistrationTests(TestCase):
    def test_citizen_can_register_and_is_logged_in(self):
        response = self.client.post(reverse("accounts:register"), registration_data())
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(User.objects.get(username="testcitizen").role, User.Role.CITIZEN)

    def test_cannot_self_register_as_super_admin(self):
        response = self.client.post(
            reverse("accounts:register"), registration_data(role="super_admin")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="testcitizen").exists())

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user("existing", "test@example.com", VALID_PASSWORD)
        response = self.client.post(reverse("accounts:register"), registration_data())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="testcitizen").exists())


class AccessTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_login_and_dashboard_for_worker(self):
        User.objects.create_user("w1", "w1@example.com", VALID_PASSWORD, role=User.Role.WORKER)
        self.assertTrue(self.client.login(username="w1", password=VALID_PASSWORD))
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Waste Worker")

    def test_superuser_gets_super_admin_role(self):
        user = User.objects.create_superuser("root", "root@example.com", VALID_PASSWORD)
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
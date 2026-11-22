"""Automated tests for the notifications app."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Notification

PASSWORD = "StrongPass#2026"


class NotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("n1", "n1@example.com", PASSWORD)
        self.other = User.objects.create_user("n2", "n2@example.com", PASSWORD)
        self.mine = Notification.objects.create(
            recipient=self.user, title="For me", message="Hello", link="/accounts/profile/"
        )
        self.theirs = Notification.objects.create(
            recipient=self.other, title="For someone else", message="Private"
        )
        self.client.login(username="n1", password=PASSWORD)

    def test_list_shows_only_own_notifications(self):
        response = self.client.get(reverse("notifications:list"))
        self.assertContains(response, "For me")
        self.assertNotContains(response, "For someone else")

    def test_unread_count_is_available_in_templates(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.context["unread_notification_count"], 1)

    def test_open_marks_read_and_redirects_to_link(self):
        response = self.client.get(reverse("notifications:open", args=[self.mine.pk]))
        self.assertRedirects(response, "/accounts/profile/")
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_read)

    def test_cannot_open_another_users_notification(self):
        response = self.client.get(reverse("notifications:open", args=[self.theirs.pk]))
        self.assertEqual(response.status_code, 404)

    def test_mark_all_read_requires_post(self):
        url = reverse("notifications:mark_all_read")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("notifications:list"))
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_read)
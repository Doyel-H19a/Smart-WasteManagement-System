"""Automated tests for the complaints app."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User
from notifications.models import Notification
from waste_management.models import Ward

from .models import Complaint

PASSWORD = "StrongPass#2026"
TEST_MEDIA_ROOT = tempfile.mkdtemp()  # uploads during tests go here, not into /media


def tearDownModule():
    shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)


def make_image(name="photo.png"):
    """Build a small valid PNG upload in memory."""
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ComplaintBaseTestCase(TestCase):
    """Shared fixtures for the complaint tests."""

    def setUp(self):
        self.ward = Ward.objects.create(ward_number=1, name="Test Ward")
        self.citizen = User.objects.create_user("cit1", "cit1@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.other_citizen = User.objects.create_user("cit2", "cit2@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.admin = User.objects.create_user("adm1", "adm1@example.com", PASSWORD, role=User.Role.MUNICIPAL_ADMIN)
        self.worker = User.objects.create_user("wrk1", "wrk1@example.com", PASSWORD, role=User.Role.WORKER)

    def form_data(self, **overrides):
        data = {
            "title": "Overflowing bin near market",
            "category": Complaint.Category.OVERFLOWING_BIN,
            "ward": self.ward.pk,
            "description": "The community bin has been overflowing for three days.",
            "address": "Gariahat Market, Kolkata",
        }
        data.update(overrides)
        return data

    def make_complaint(self, citizen=None, **overrides):
        values = {
            "citizen": citizen or self.citizen,
            "ward": self.ward,
            "title": "Test complaint",
            "category": Complaint.Category.OTHER,
            "description": "A description that is long enough to be valid.",
            "address": "Test street",
        }
        values.update(overrides)
        return Complaint.objects.create(**values)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ComplaintSubmissionTests(ComplaintBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="cit1", password=PASSWORD)
        self.url = reverse("complaints:create")

    def test_citizen_can_submit_complaint_with_image(self):
        response = self.client.post(self.url, self.form_data(image=make_image()))
        complaint = Complaint.objects.get()
        self.assertRedirects(response, reverse("complaints:detail", args=[complaint.pk]))
        self.assertEqual(complaint.citizen, self.citizen)
        self.assertEqual(complaint.status, Complaint.Status.SUBMITTED)
        self.assertTrue(complaint.image.name.startswith("complaints/"))

    def test_submission_creates_history_and_notifications(self):
        self.client.post(self.url, self.form_data())
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.history.count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.citizen).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists())

    def test_short_description_is_rejected(self):
        response = self.client.post(self.url, self.form_data(description="Too short"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_non_image_upload_is_rejected(self):
        bad_file = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(self.url, self.form_data(image=bad_file))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_coordinates_must_be_given_together(self):
        response = self.client.post(self.url, self.form_data(latitude="22.5"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_inactive_ward_cannot_be_selected(self):
        closed = Ward.objects.create(ward_number=2, name="Closed Ward", is_active=False)
        response = self.client.post(self.url, self.form_data(ward=closed.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)


class ComplaintAccessTests(ComplaintBaseTestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("complaints:create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_worker_cannot_open_complaint_form(self):
        self.client.login(username="wrk1", password=PASSWORD)
        response = self.client.get(reverse("complaints:create"))
        self.assertEqual(response.status_code, 403)

    def test_citizen_cannot_view_another_citizens_complaint(self):
        complaint = self.make_complaint(citizen=self.other_citizen)
        self.client.login(username="cit1", password=PASSWORD)
        response = self.client.get(reverse("complaints:detail", args=[complaint.pk]))
        self.assertEqual(response.status_code, 403)

    def test_municipal_admin_can_view_any_complaint(self):
        complaint = self.make_complaint(title="Visible to staff")
        self.client.login(username="adm1", password=PASSWORD)
        response = self.client.get(reverse("complaints:detail", args=[complaint.pk]))
        self.assertContains(response, "Visible to staff")

    def test_list_shows_only_own_complaints(self):
        self.make_complaint(title="Alpha heap")
        self.make_complaint(citizen=self.other_citizen, title="Beta heap")
        self.client.login(username="cit1", password=PASSWORD)
        response = self.client.get(reverse("complaints:list"))
        self.assertContains(response, "Alpha heap")
        self.assertNotContains(response, "Beta heap")

    def test_status_filter(self):
        self.make_complaint(title="Alpha heap")
        self.make_complaint(title="Gamma heap", status=Complaint.Status.RESOLVED)
        self.client.login(username="cit1", password=PASSWORD)
        response = self.client.get(reverse("complaints:list"), {"status": "resolved"})
        self.assertContains(response, "Gamma heap")
        self.assertNotContains(response, "Alpha heap")
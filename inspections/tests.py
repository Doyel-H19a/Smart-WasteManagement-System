"""Tests for inspections."""
import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from notifications.models import Notification
from waste_management.models import Ward

from .models import Inspection

PASSWORD = "StrongPass#2026"
TEST_MEDIA_ROOT = tempfile.mkdtemp()  # uploads during tests go here, not into /media


def tearDownModule():
    shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)


def make_user(username, role):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD, role=role)


def make_photo(name="inspection.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class InspectionBase(TestCase):
    """Shared fixtures: one ward and one user per role used in these tests."""

    def setUp(self):
        self.ward = Ward.objects.create(ward_number=1, name="Alpha Ward")
        self.officer = make_user("ins_ho", User.Role.HEALTH_OFFICER)
        self.officer2 = make_user("ins_ho2", User.Role.HEALTH_OFFICER)
        self.admin = make_user("ins_adm", User.Role.MUNICIPAL_ADMIN)
        self.executive = make_user("ins_exec", User.Role.EXECUTIVE_OFFICER)
        self.bulk = make_user("ins_bulk1", User.Role.BULK_GENERATOR)
        self.bulk2 = make_user("ins_bulk2", User.Role.BULK_GENERATOR)
        self.citizen = make_user("ins_cit", User.Role.CITIZEN)
        self.worker = make_user("ins_wrk", User.Role.WORKER)

    # --- helpers ------------------------------------------------------------
    def login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=PASSWORD))

    def form_data(self, **overrides):
        data = {
            "category": "public_area",
            "ward": self.ward.pk,
            "premises_name": "Market lane bins",
            "address": "Gariahat market lane, Kolkata",
            "inspection_date": timezone.localdate().isoformat(),
            "segregation_rating": 3,
            "cleanliness_rating": 4,
            "bin_condition_rating": 3,
            "outcome": "minor_issues",
            "findings": "Bins were overflowing and waste was not segregated.",
            "recommendations": "",
        }
        data.update(overrides)
        return data

    def make_inspection(self, **overrides):
        values = {
            "inspector": self.officer, "ward": self.ward, "category": "public_area",
            "premises_name": "Test place", "address": "Test street",
            "inspection_date": timezone.localdate(),
            "segregation_rating": 3, "cleanliness_rating": 3, "bin_condition_rating": 3,
            "outcome": "minor_issues", "findings": "Some findings were noted here.",
        }
        values.update(overrides)
        return Inspection.objects.create(**values)


class RecordInspectionTests(InspectionBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("inspections:create")
        self.login("ins_ho")

    def test_health_officer_records_inspection_with_photo(self):
        response = self.client.post(self.url, self.form_data(photo=make_photo()))
        inspection = Inspection.objects.get()
        self.assertRedirects(response, reverse("inspections:detail", args=[inspection.pk]))
        self.assertEqual(inspection.inspector, self.officer)
        self.assertTrue(inspection.photo.name.startswith("inspections/"))

    def test_bulk_premises_requires_registered_generator(self):
        response = self.client.post(self.url, self.form_data(category="bulk_premises"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_generator_only_allowed_for_bulk_premises(self):
        response = self.client.post(self.url, self.form_data(bulk_generator=self.bulk.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_future_inspection_date_is_rejected(self):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(self.url, self.form_data(inspection_date=tomorrow))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_follow_up_requires_a_date(self):
        response = self.client.post(self.url, self.form_data(follow_up_required="on"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_follow_up_cannot_precede_the_inspection(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.post(
            self.url, self.form_data(follow_up_required="on", follow_up_date=yesterday)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_ratings_must_be_between_1_and_5(self):
        response = self.client.post(self.url, self.form_data(segregation_rating=6))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_non_image_photo_is_rejected(self):
        bad_file = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(self.url, self.form_data(photo=bad_file))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_coordinates_must_be_given_together(self):
        response = self.client.post(self.url, self.form_data(latitude="22.5"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_only_health_officers_can_record(self):
        for username in ("ins_adm", "ins_cit", "ins_bulk1"):
            self.login(username)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_inspected_generator_is_notified(self):
        self.client.post(
            self.url, self.form_data(category="bulk_premises", bulk_generator=self.bulk.pk)
        )
        self.assertTrue(Notification.objects.filter(recipient=self.bulk).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.bulk2).exists())

    def test_major_violation_notifies_municipal_admins(self):
        self.client.post(self.url, self.form_data(outcome="major_violation"))
        self.assertTrue(
            Notification.objects.filter(recipient=self.admin, title__icontains="Major violation").exists()
        )


class InspectionAccessTests(InspectionBase):
    def test_list_visibility_by_role(self):
        grand = self.make_inspection(
            category="bulk_premises", premises_name="Grand Premises", bulk_generator=self.bulk
        )
        public = self.make_inspection(premises_name="Public lane")

        def listed(username):
            self.login(username)
            response = self.client.get(reverse("inspections:list"))
            return {i.pk for i in response.context["page_obj"]}

        everything = {grand.pk, public.pk}
        self.assertEqual(listed("ins_ho"), everything)
        self.assertEqual(listed("ins_adm"), everything)
        self.assertEqual(listed("ins_exec"), everything)
        self.assertEqual(listed("ins_bulk1"), {grand.pk})
        self.assertEqual(listed("ins_bulk2"), set())

        for username in ("ins_cit", "ins_wrk"):
            self.login(username)
            self.assertEqual(self.client.get(reverse("inspections:list")).status_code, 403)

    def test_generator_cannot_open_other_premises_detail(self):
        inspection = self.make_inspection(
            category="bulk_premises", premises_name="Grand Premises", bulk_generator=self.bulk
        )
        url = reverse("inspections:detail", args=[inspection.pk])

        self.login("ins_bulk1")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.login("ins_bulk2")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login("ins_cit")
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_follow_up_can_be_completed_once(self):
        inspection = self.make_inspection(
            follow_up_required=True, follow_up_date=timezone.localdate() + timedelta(days=3)
        )
        url = reverse("inspections:follow_up_done", args=[inspection.pk])

        self.login("ins_ho2")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("inspections:detail", args=[inspection.pk]))
        inspection.refresh_from_db()
        self.assertIsNotNone(inspection.follow_up_completed_at)
        self.assertEqual(inspection.follow_up_completed_by, self.officer2)

        first_time = inspection.follow_up_completed_at
        self.client.post(url)
        inspection.refresh_from_db()
        self.assertEqual(inspection.follow_up_completed_at, first_time)

        self.login("ins_adm")
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_follow_up_is_refused_when_none_was_requested(self):
        inspection = self.make_inspection()
        self.login("ins_ho")
        self.client.post(reverse("inspections:follow_up_done", args=[inspection.pk]))
        inspection.refresh_from_db()
        self.assertIsNone(inspection.follow_up_completed_at)

    def test_outcome_filter_and_summary(self):
        self.make_inspection(outcome="compliant")
        self.make_inspection(outcome="minor_issues")
        self.make_inspection(outcome="major_violation")
        self.login("ins_adm")

        response = self.client.get(reverse("inspections:list"))
        summary = response.context["summary"]
        self.assertEqual(
            (summary["count"], summary["compliant"], summary["minor"], summary["major"]), (3, 1, 1, 1)
        )

        response = self.client.get(reverse("inspections:list"), {"outcome": "major_violation"})
        self.assertEqual(response.context["summary"]["count"], 1)

    def test_pending_follow_up_filter(self):
        soon = timezone.localdate() + timedelta(days=2)
        pending = self.make_inspection(follow_up_required=True, follow_up_date=soon)
        self.make_inspection(
            follow_up_required=True, follow_up_date=soon, follow_up_completed_at=timezone.now()
        )
        self.make_inspection()
        self.login("ins_ho")
        response = self.client.get(reverse("inspections:list"), {"follow_up": "pending"})
        self.assertEqual([i.pk for i in response.context["page_obj"]], [pending.pk])
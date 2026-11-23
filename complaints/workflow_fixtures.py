"""Shared fixtures for the Phase 3 workflow tests (not a test module itself)."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import User
from complaints import services
from complaints.models import Complaint
from waste_management.models import Ward

PASSWORD = "StrongPass#2026"


def make_image(name="proof.png"):
    """Build a small valid PNG upload in memory."""
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class WorkflowTestCase(TestCase):
    """Creates a ward, four users and one freshly submitted complaint."""

    @classmethod
    def setUpClass(cls):
        # Uploaded files during tests go to a temporary folder, not into /media.
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)

    def setUp(self):
        self.ward = Ward.objects.create(ward_number=1, name="Test Ward")
        self.citizen = User.objects.create_user("cit1", "cit1@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.admin = User.objects.create_user("adm1", "adm1@example.com", PASSWORD, role=User.Role.MUNICIPAL_ADMIN)
        self.worker = User.objects.create_user("wrk1", "wrk1@example.com", PASSWORD, role=User.Role.WORKER)
        self.other_worker = User.objects.create_user("wrk2", "wrk2@example.com", PASSWORD, role=User.Role.WORKER)

        complaint = Complaint(
            citizen=self.citizen,
            ward=self.ward,
            title="Overflowing bin near market",
            category=Complaint.Category.OVERFLOWING_BIN,
            description="The community bin has been overflowing for three days.",
            address="Gariahat Market, Kolkata",
        )
        self.complaint = services.submit_complaint(complaint)

    # --- helpers ------------------------------------------------------------
    def login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=PASSWORD))

    def refresh(self):
        self.complaint.refresh_from_db()
        return self.complaint

    def assertStatus(self, status):
        self.assertEqual(self.refresh().status, status)

    # Move the complaint to a given stage using the real services.
    def to_under_review(self):
        services.start_review(self.complaint, self.admin)

    def to_assigned(self):
        self.to_under_review()
        services.assign_worker(self.complaint, self.admin, self.worker, Complaint.Priority.MEDIUM, "")

    def to_accepted(self):
        self.to_assigned()
        services.accept_assignment(self.complaint, self.worker)

    def to_completed(self):
        self.to_accepted()
        services.complete_task(self.complaint, self.worker, "Waste collected and area cleaned.", make_image())
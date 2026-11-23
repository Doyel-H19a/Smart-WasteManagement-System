"""Tests for the AI classification interface (demonstration mode)."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User

from .classifier import WASTE_CLASSES, DemoClassifier
from .models import WasteClassification

PASSWORD = "StrongPass#2026"
TEST_MEDIA_ROOT = tempfile.mkdtemp()  # uploads during tests go here, not into /media


def tearDownModule():
    shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)


def png_bytes(color="green"):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_upload(name="waste.png", color="green"):
    return SimpleUploadedFile(name, png_bytes(color), content_type="image/png")


class DemoClassifierTests(TestCase):
    def test_demo_result_is_deterministic_and_flagged_as_demo(self):
        first = DemoClassifier().classify(png_bytes())
        second = DemoClassifier().classify(png_bytes())
        self.assertEqual(first, second)
        self.assertTrue(first.is_demo)
        self.assertIn(first.label, WASTE_CLASSES)
        self.assertTrue(0.55 <= first.confidence <= 0.95)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ClassificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cit1", "cit1@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.other = User.objects.create_user("cit2", "cit2@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.admin = User.objects.create_user("adm1", "adm1@example.com", PASSWORD, role=User.Role.MUNICIPAL_ADMIN)
        self.url = reverse("ai_classification:classify")

    def upload_as(self, username):
        self.client.login(username=username, password=PASSWORD)
        return self.client.post(self.url, {"image": make_upload()})

    def test_classify_page_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_upload_stores_demo_result_and_shows_demo_banner(self):
        response = self.upload_as("cit1")
        record = WasteClassification.objects.get()
        self.assertRedirects(response, reverse("ai_classification:result", args=[record.pk]))
        self.assertTrue(record.is_demo)
        self.assertEqual(record.backend, "demo")
        result_page = self.client.get(response["Location"])
        self.assertContains(result_page, "DEMONSTRATION MODE")

    def test_non_image_is_rejected(self):
        self.client.login(username="cit1", password=PASSWORD)
        bad_file = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(self.url, {"image": bad_file})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteClassification.objects.count(), 0)

    def test_other_user_cannot_view_result(self):
        self.upload_as("cit1")
        record = WasteClassification.objects.get()
        self.client.logout()
        self.client.login(username="cit2", password=PASSWORD)
        response = self.client.get(reverse("ai_classification:result", args=[record.pk]))
        self.assertEqual(response.status_code, 403)

    def test_municipal_admin_can_view_result(self):
        self.upload_as("cit1")
        record = WasteClassification.objects.get()
        self.client.logout()
        self.client.login(username="adm1", password=PASSWORD)
        response = self.client.get(reverse("ai_classification:result", args=[record.pk]))
        self.assertEqual(response.status_code, 200)

    @override_settings(AI_CLASSIFIER_BACKEND="keras", AI_MODEL_PATH="/nonexistent/model.keras")
    def test_keras_backend_without_model_fails_clearly_and_saves_nothing(self):
        self.client.login(username="cit1", password=PASSWORD)
        response = self.client.post(self.url, {"image": make_upload()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No trained model found")
        self.assertEqual(WasteClassification.objects.count(), 0)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ClassificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("api1", "api1@example.com", PASSWORD, role=User.Role.CITIZEN)
        self.url = reverse("ai_classification:api_classify")

    def test_api_returns_demo_result(self):
        self.client.login(username="api1", password=PASSWORD)
        response = self.client.post(self.url, {"image": make_upload()})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_demo"])
        self.assertIn(data["label"], WASTE_CLASSES)
        self.assertTrue(data["notice"])

    def test_api_requires_login(self):
        response = self.client.post(self.url, {"image": make_upload()})
        self.assertEqual(response.status_code, 403)
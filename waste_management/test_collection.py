"""Tests for collection schedules and waste movement monitoring."""
from datetime import time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification

from . import services
from .models import CollectionSchedule, Ward, WasteMovement

PASSWORD = "StrongPass#2026"


def make_user(username, role):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD, role=role)


class CollectionBase(TestCase):
    """Shared fixtures: two wards and users for each role used in these tests."""

    def setUp(self):
        self.ward = Ward.objects.create(ward_number=1, name="Alpha Ward")
        self.other_ward = Ward.objects.create(ward_number=2, name="Beta Ward")
        self.admin = make_user("col_admin", User.Role.MUNICIPAL_ADMIN)
        self.worker = make_user("col_w1", User.Role.WORKER)
        self.worker2 = make_user("col_w2", User.Role.WORKER)
        self.citizen = make_user("col_cit", User.Role.CITIZEN)

    # --- helpers ------------------------------------------------------------
    def login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=PASSWORD))

    def make_schedule(self, **overrides):
        values = {
            "ward": self.ward, "route_name": "Main Road route", "waste_type": "wet",
            "weekday": 0, "start_time": time(6, 0), "end_time": time(9, 0),
            "assigned_worker": self.worker, "vehicle_number": "WB-01", "is_active": True,
        }
        values.update(overrides)
        return CollectionSchedule.objects.create(**values)

    def schedule_form(self, **overrides):
        data = {
            "ward": self.ward.pk, "route_name": "Main Road route", "waste_type": "wet",
            "weekday": 0, "start_time": "06:00", "end_time": "09:00",
            "assigned_worker": self.worker.pk, "vehicle_number": "WB-01",
            "notes": "", "is_active": "on",
        }
        data.update(overrides)
        return data

    def make_movement(self, **overrides):
        values = {
            "movement_type": "pickup", "waste_type": "wet", "quantity_kg": Decimal("100.00"),
            "ward": self.ward, "from_location": "Alpha point", "to_location": "Vehicle",
            "logged_by": self.worker,
        }
        values.update(overrides)
        return WasteMovement.objects.create(**values)

    def movement_form(self, **overrides):
        data = {
            "movement_type": "pickup", "waste_type": "wet", "quantity_kg": "120.50",
            "ward": self.ward.pk, "from_location": "Alpha market point",
            "to_location": "Collection vehicle", "vehicle_number": "WB-01", "notes": "",
        }
        data.update(overrides)
        return data


class ScheduleTests(CollectionBase):
    def test_admin_creates_schedule_and_worker_is_notified(self):
        self.login("col_admin")
        response = self.client.post(reverse("collection:schedule_create"), self.schedule_form())
        self.assertRedirects(response, reverse("collection:schedule_list"))
        schedule = CollectionSchedule.objects.get()
        self.assertEqual(schedule.created_by, self.admin)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.worker, category=Notification.Category.TASK
            ).exists()
        )

    def test_end_time_must_be_after_start_time(self):
        self.login("col_admin")
        response = self.client.post(
            reverse("collection:schedule_create"), self.schedule_form(end_time="05:00")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CollectionSchedule.objects.count(), 0)

    def test_duplicate_schedule_is_rejected(self):
        self.make_schedule()
        self.login("col_admin")
        response = self.client.post(reverse("collection:schedule_create"), self.schedule_form())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CollectionSchedule.objects.count(), 1)

    def test_citizen_cannot_create_schedule(self):
        self.login("col_cit")
        self.assertEqual(self.client.get(reverse("collection:schedule_create")).status_code, 403)

    def test_worker_sees_only_own_active_schedules(self):
        self.make_schedule(route_name="Mine route")
        self.make_schedule(route_name="Theirs route", assigned_worker=self.worker2)
        self.make_schedule(route_name="Dormant route", is_active=False)
        self.login("col_w1")
        response = self.client.get(reverse("collection:schedule_list"))
        self.assertContains(response, "Mine route")
        self.assertNotContains(response, "Theirs route")
        self.assertNotContains(response, "Dormant route")

    def test_citizen_sees_only_active_schedules_without_worker_names(self):
        self.make_schedule(route_name="Active route")
        self.make_schedule(route_name="Retired route", is_active=False)
        self.login("col_cit")
        response = self.client.get(reverse("collection:schedule_list"))
        self.assertContains(response, "Active route")
        self.assertNotContains(response, "Retired route")
        self.assertNotContains(response, "col_w1")

    def test_reassigning_notifies_new_and_previous_worker(self):
        schedule = self.make_schedule()
        self.login("col_admin")
        self.client.post(
            reverse("collection:schedule_update", args=[schedule.pk]),
            self.schedule_form(assigned_worker=self.worker2.pk),
        )
        schedule.refresh_from_db()
        self.assertEqual(schedule.assigned_worker, self.worker2)
        self.assertTrue(
            Notification.objects.filter(recipient=self.worker2, title__icontains="New collection").exists()
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.worker, title__icontains="reassigned").exists()
        )

    def test_toggle_requires_post_and_deactivates(self):
        schedule = self.make_schedule()
        url = reverse("collection:schedule_toggle", args=[schedule.pk])
        self.login("col_admin")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("collection:schedule_list"))
        schedule.refresh_from_db()
        self.assertFalse(schedule.is_active)
        self.assertTrue(
            Notification.objects.filter(recipient=self.worker, title__icontains="cancelled").exists()
        )

    def test_worker_cannot_manage_schedules(self):
        schedule = self.make_schedule()
        self.login("col_w1")
        response = self.client.post(reverse("collection:schedule_toggle", args=[schedule.pk]))
        self.assertEqual(response.status_code, 403)
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_active)


class MovementTests(CollectionBase):
    def test_worker_logs_pickup_linked_to_own_schedule(self):
        schedule = self.make_schedule()
        self.login("col_w1")
        response = self.client.post(
            reverse("collection:movement_create"), self.movement_form(schedule=schedule.pk)
        )
        self.assertRedirects(response, reverse("collection:movement_list"))
        movement = WasteMovement.objects.get()
        self.assertEqual(movement.logged_by, self.worker)
        self.assertEqual(movement.schedule, schedule)

    def test_cannot_link_another_workers_schedule(self):
        schedule = self.make_schedule(assigned_worker=self.worker2)
        self.login("col_w1")
        response = self.client.post(
            reverse("collection:movement_create"), self.movement_form(schedule=schedule.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteMovement.objects.count(), 0)

    def test_schedule_ward_must_match_movement_ward(self):
        schedule = self.make_schedule()
        self.login("col_w1")
        response = self.client.post(
            reverse("collection:movement_create"),
            self.movement_form(schedule=schedule.pk, ward=self.other_ward.pk),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteMovement.objects.count(), 0)

    def test_quantity_must_be_positive(self):
        self.login("col_w1")
        response = self.client.post(
            reverse("collection:movement_create"), self.movement_form(quantity_kg="0")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteMovement.objects.count(), 0)

    def test_coordinates_must_be_given_together(self):
        self.login("col_w1")
        response = self.client.post(
            reverse("collection:movement_create"), self.movement_form(latitude="22.5")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteMovement.objects.count(), 0)

    def test_only_workers_can_log_movements(self):
        self.login("col_admin")
        self.assertEqual(self.client.get(reverse("collection:movement_create")).status_code, 403)

    def test_movement_visibility_by_role(self):
        self.make_movement(from_location="Alpha dump point")
        self.make_movement(from_location="Beta dump point", logged_by=self.worker2)

        self.login("col_w1")
        response = self.client.get(reverse("collection:movement_list"))
        self.assertContains(response, "Alpha dump point")
        self.assertNotContains(response, "Beta dump point")

        self.login("col_admin")
        response = self.client.get(reverse("collection:movement_list"))
        self.assertContains(response, "Alpha dump point")
        self.assertContains(response, "Beta dump point")

        self.login("col_cit")
        self.assertEqual(self.client.get(reverse("collection:movement_list")).status_code, 403)

    def test_list_totals_and_type_filter(self):
        self.make_movement(movement_type="pickup", quantity_kg=Decimal("100.50"))
        self.make_movement(movement_type="transfer", quantity_kg=Decimal("250.00"))
        self.login("col_admin")

        response = self.client.get(reverse("collection:movement_list"))
        self.assertEqual(response.context["summary"]["total_kg"], Decimal("350.50"))

        response = self.client.get(reverse("collection:movement_list"), {"type": "transfer"})
        self.assertEqual(response.context["summary"]["total_kg"], Decimal("250.00"))
        self.assertEqual(response.context["summary"]["pickup_kg"], Decimal("0"))

    def test_map_is_scoped_to_role(self):
        located = {"latitude": Decimal("22.520000"), "longitude": Decimal("88.360000")}
        self.make_movement(**located)
        self.make_movement(logged_by=self.worker2, **located)
        self.make_movement()  # no coordinates

        self.login("col_w1")
        response = self.client.get(reverse("collection:movement_map"))
        self.assertEqual(len(response.context["map_data"]["movements"]), 1)
        self.assertEqual(response.context["missing_count"], 1)

        self.login("col_admin")
        response = self.client.get(reverse("collection:movement_map"))
        self.assertEqual(len(response.context["map_data"]["movements"]), 2)

        self.login("col_cit")
        self.assertEqual(self.client.get(reverse("collection:movement_map")).status_code, 403)

    def test_log_form_is_prefilled_from_own_schedule(self):
        schedule = self.make_schedule()
        self.login("col_w1")
        response = self.client.get(reverse("collection:movement_create"), {"schedule": schedule.pk})
        self.assertEqual(response.context["form"].initial["ward"], self.ward.pk)
        self.assertEqual(response.context["form"].initial["schedule"], schedule.pk)

    def test_service_rejects_schedule_of_another_worker(self):
        schedule = self.make_schedule(assigned_worker=self.worker2)
        movement = WasteMovement(
            movement_type="pickup", waste_type="wet", quantity_kg=Decimal("10.00"),
            ward=self.ward, schedule=schedule, from_location="A", to_location="B",
        )
        with self.assertRaises(services.MovementError):
            services.log_movement(movement, self.worker)
        self.assertEqual(WasteMovement.objects.count(), 0)
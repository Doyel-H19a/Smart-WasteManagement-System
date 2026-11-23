"""Tests for penalties."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from inspections.models import Inspection
from notifications.models import Notification
from waste_management.models import Ward

from . import services
from .models import Penalty

PASSWORD = "StrongPass#2026"
Status = Penalty.Status


def make_user(username, role):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD, role=role)


class PenaltyBase(TestCase):
    """Shared fixtures: two wards and one user per role used in these tests."""

    def setUp(self):
        self.ward = Ward.objects.create(ward_number=1, name="Alpha Ward")
        self.other_ward = Ward.objects.create(ward_number=2, name="Beta Ward")
        self.officer = make_user("pen_ho", User.Role.HEALTH_OFFICER)
        self.admin = make_user("pen_adm1", User.Role.MUNICIPAL_ADMIN)
        self.admin2 = make_user("pen_adm2", User.Role.MUNICIPAL_ADMIN)
        self.superadmin = make_user("pen_sup", User.Role.SUPER_ADMIN)
        self.executive = make_user("pen_exec", User.Role.EXECUTIVE_OFFICER)
        self.citizen = make_user("pen_cit1", User.Role.CITIZEN)
        self.citizen2 = make_user("pen_cit2", User.Role.CITIZEN)
        self.bulk = make_user("pen_bulk", User.Role.BULK_GENERATOR)
        self.worker = make_user("pen_worker", User.Role.WORKER)

    # --- helpers ------------------------------------------------------------
    def login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=PASSWORD))

    def url(self, name, penalty):
        return reverse(f"penalties:{name}", args=[penalty.pk])

    def days_from_today(self, days):
        return timezone.localdate() + timedelta(days=days)

    def form_data(self, **overrides):
        data = {
            "issued_to": self.citizen.pk,
            "ward": self.ward.pk,
            "violation_type": "illegal_dumping",
            "description": "Waste was dumped on the footpath near the market.",
            "amount": "500.00",
            "due_date": self.days_from_today(14).isoformat(),
        }
        data.update(overrides)
        return data

    def make_penalty(self, **overrides):
        values = {
            "issued_to": self.citizen, "issued_by": self.officer, "ward": self.ward,
            "violation_type": Penalty.Violation.ILLEGAL_DUMPING,
            "description": "Waste was dumped on the footpath near the market.",
            "amount": Decimal("500.00"), "due_date": self.days_from_today(14),
            "status": Status.ISSUED,
        }
        values.update(overrides)
        return Penalty.objects.create(**values)

    def make_inspection(self, **overrides):
        values = {
            "inspector": self.officer, "ward": self.ward, "category": "bulk_premises",
            "premises_name": "Grand Premises", "address": "Camac Street",
            "bulk_generator": self.bulk, "inspection_date": timezone.localdate(),
            "segregation_rating": 2, "cleanliness_rating": 3, "bin_condition_rating": 2,
            "outcome": "major_violation", "findings": "Mixed waste in bulk containers.",
        }
        values.update(overrides)
        return Inspection.objects.create(**values)


class IssuePenaltyTests(PenaltyBase):
    def setUp(self):
        super().setUp()
        self.create_url = reverse("penalties:create")

    def test_health_officer_issues_penalty_and_recipient_is_notified(self):
        self.login("pen_ho")
        response = self.client.post(self.create_url, self.form_data())
        penalty = Penalty.objects.get()
        self.assertRedirects(response, reverse("penalties:detail", args=[penalty.pk]))
        self.assertEqual(penalty.issued_by, self.officer)
        self.assertEqual(penalty.status, Status.ISSUED)
        self.assertEqual(penalty.events.count(), 1)
        self.assertTrue(
            Notification.objects.filter(recipient=self.citizen, title__icontains="issued").exists()
        )

    def test_municipal_admin_can_also_issue_penalties(self):
        self.login("pen_adm1")
        self.client.post(self.create_url, self.form_data())
        self.assertEqual(Penalty.objects.get().issued_by, self.admin)

    def test_other_roles_cannot_issue_penalties(self):
        for username in ("pen_cit1", "pen_worker", "pen_exec", "pen_sup"):
            self.login(username)
            self.assertEqual(self.client.get(self.create_url).status_code, 403)

    def test_due_date_cannot_be_in_the_past(self):
        self.login("pen_ho")
        response = self.client.post(
            self.create_url, self.form_data(due_date=self.days_from_today(-1).isoformat())
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Penalty.objects.count(), 0)

    def test_amount_must_be_within_limits(self):
        self.login("pen_ho")
        for amount in ("0", "100001"):
            response = self.client.post(self.create_url, self.form_data(amount=amount))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Penalty.objects.count(), 0)

    def test_staff_cannot_be_penalised(self):
        self.login("pen_ho")
        response = self.client.post(self.create_url, self.form_data(issued_to=self.worker.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Penalty.objects.count(), 0)

    def test_linked_inspection_must_match_ward_and_generator(self):
        inspection = self.make_inspection()
        self.login("pen_ho")

        wrong_ward = self.form_data(
            issued_to=self.bulk.pk, ward=self.other_ward.pk, inspection=inspection.pk
        )
        self.assertEqual(self.client.post(self.create_url, wrong_ward).status_code, 200)

        wrong_person = self.form_data(issued_to=self.citizen.pk, inspection=inspection.pk)
        self.assertEqual(self.client.post(self.create_url, wrong_person).status_code, 200)
        self.assertEqual(Penalty.objects.count(), 0)

        correct = self.form_data(issued_to=self.bulk.pk, inspection=inspection.pk)
        self.client.post(self.create_url, correct)
        self.assertEqual(Penalty.objects.get().inspection, inspection)

    def test_create_form_is_prefilled_from_inspection(self):
        inspection = self.make_inspection()
        self.login("pen_ho")
        response = self.client.get(self.create_url, {"inspection": inspection.pk})
        initial = response.context["form"].initial
        self.assertEqual(initial["issued_to"], self.bulk.pk)
        self.assertEqual(initial["ward"], self.ward.pk)
        self.assertEqual(initial["inspection"], inspection.pk)


class PenaltyVisibilityTests(PenaltyBase):
    def listed(self, username, **params):
        self.login(username)
        response = self.client.get(reverse("penalties:list"), params)
        return {p.pk for p in response.context["page_obj"]}

    def test_recipient_sees_only_own_penalties(self):
        own = self.make_penalty()
        self.make_penalty(issued_to=self.citizen2)
        self.assertEqual(self.listed("pen_cit1"), {own.pk})

    def test_other_citizen_cannot_open_penalty(self):
        penalty = self.make_penalty()
        self.login("pen_cit2")
        self.assertEqual(self.client.get(self.url("detail", penalty)).status_code, 403)
        self.login("pen_cit1")
        self.assertEqual(self.client.get(self.url("detail", penalty)).status_code, 200)

    def test_staff_see_all_penalties_with_filters(self):
        first = self.make_penalty()
        second = self.make_penalty(issued_to=self.bulk, status=Status.PAID)
        both = {first.pk, second.pk}
        self.assertEqual(self.listed("pen_adm1"), both)
        self.assertEqual(self.listed("pen_ho"), both)
        self.assertEqual(self.listed("pen_adm1", status="paid"), {second.pk})
        self.assertEqual(self.listed("pen_adm1", q="pen_bulk"), {second.pk})

    def test_executive_officer_is_read_only(self):
        penalty = self.make_penalty()
        self.login("pen_exec")
        self.assertEqual(self.client.get(self.url("detail", penalty)).status_code, 200)
        self.assertEqual(
            self.client.post(self.url("pay", penalty), {"pay-reference": "RCPT-1"}).status_code, 403
        )
        self.assertEqual(
            self.client.post(self.url("waive", penalty), {"waive-reason": "Not valid anyway."}).status_code, 403
        )
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

    def test_workers_cannot_open_penalties(self):
        penalty = self.make_penalty()
        self.login("pen_worker")
        self.assertEqual(self.client.get(reverse("penalties:list")).status_code, 403)
        self.assertEqual(self.client.get(self.url("detail", penalty)).status_code, 403)


class DisputeTests(PenaltyBase):
    def test_recipient_disputes_and_staff_are_notified(self):
        penalty = self.make_penalty()
        self.login("pen_cit1")
        response = self.client.post(
            self.url("dispute", penalty), {"dispute-reason": "I was out of the city on that day."}
        )
        self.assertRedirects(response, self.url("detail", penalty))
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.DISPUTED)
        self.assertIsNotNone(penalty.disputed_at)
        self.assertTrue(Notification.objects.filter(recipient=self.admin, title__icontains="disputed").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.officer, title__icontains="disputed").exists())

    def test_dispute_needs_a_proper_reason(self):
        penalty = self.make_penalty()
        self.login("pen_cit1")
        response = self.client.post(self.url("dispute", penalty), {"dispute-reason": "no"})
        self.assertEqual(response.status_code, 200)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

    def test_other_user_cannot_dispute(self):
        penalty = self.make_penalty()
        self.login("pen_cit2")
        response = self.client.post(
            self.url("dispute", penalty), {"dispute-reason": "This was not my penalty at all."}
        )
        self.assertEqual(response.status_code, 404)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

    def test_cannot_dispute_twice_or_after_payment(self):
        paid = self.make_penalty(status=Status.PAID)
        used = self.make_penalty(disputed_at=timezone.now(), dispute_reason="An earlier dispute reason.")
        self.login("pen_cit1")
        for penalty in (paid, used):
            self.client.post(
                self.url("dispute", penalty), {"dispute-reason": "I want to dispute this again."}
            )
        paid.refresh_from_db()
        used.refresh_from_db()
        self.assertEqual(paid.status, Status.PAID)
        self.assertEqual(used.status, Status.ISSUED)


class ResolutionTests(PenaltyBase):
    def test_admin_records_payment(self):
        penalty = self.make_penalty()
        self.login("pen_adm1")
        response = self.client.post(self.url("pay", penalty), {"pay-reference": "RCPT-1001"})
        self.assertRedirects(response, self.url("detail", penalty))
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.PAID)
        self.assertEqual(penalty.payment_reference, "RCPT-1001")
        self.assertEqual(penalty.recorded_by, self.admin)
        self.assertIsNotNone(penalty.paid_at)
        self.assertTrue(
            Notification.objects.filter(recipient=self.citizen, title__icontains="payment").exists()
        )

    def test_payment_requires_reference_and_issued_status(self):
        penalty = self.make_penalty()
        disputed = self.make_penalty(status=Status.DISPUTED, disputed_at=timezone.now())
        self.login("pen_adm1")

        response = self.client.post(self.url("pay", penalty), {"pay-reference": ""})
        self.assertEqual(response.status_code, 200)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

        self.client.post(self.url("pay", disputed), {"pay-reference": "RCPT-2002"})
        disputed.refresh_from_db()
        self.assertEqual(disputed.status, Status.DISPUTED)

    def test_health_officer_cannot_record_payment_or_waive(self):
        penalty = self.make_penalty()
        self.login("pen_ho")
        self.assertEqual(
            self.client.post(self.url("pay", penalty), {"pay-reference": "RCPT-3003"}).status_code, 403
        )
        self.assertEqual(
            self.client.post(self.url("waive", penalty), {"waive-reason": "Not needed anymore."}).status_code, 403
        )
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

    def test_waive_requires_reason_and_notifies_recipient(self):
        penalty = self.make_penalty()
        self.login("pen_adm1")

        response = self.client.post(self.url("waive", penalty), {"waive-reason": ""})
        self.assertEqual(response.status_code, 200)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

        self.client.post(self.url("waive", penalty), {"waive-reason": "Issued to the wrong household."})
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.WAIVED)
        self.assertEqual(penalty.resolution_note, "Issued to the wrong household.")
        self.assertTrue(
            Notification.objects.filter(recipient=self.citizen, title__icontains="waived").exists()
        )

    def test_issuer_cannot_resolve_own_penalty(self):
        penalty = self.make_penalty(issued_by=self.admin)
        data = {"waive-reason": "Changed my mind about this."}

        self.login("pen_adm1")
        self.client.post(self.url("waive", penalty), data)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)

        self.login("pen_adm2")
        self.client.post(self.url("waive", penalty), data)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.WAIVED)
        self.assertEqual(penalty.resolved_by, self.admin2)

    def test_reject_dispute_restores_penalty_with_new_due_date(self):
        penalty = self.make_penalty(
            status=Status.DISPUTED, disputed_at=timezone.now(), dispute_reason="I was not in the city."
        )
        new_date = self.days_from_today(10)
        self.login("pen_adm1")
        self.client.post(
            self.url("reject_dispute", penalty),
            {"reject-note": "Photo evidence confirms the violation.",
             "reject-new_due_date": new_date.isoformat()},
        )
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.ISSUED)
        self.assertEqual(penalty.due_date, new_date)
        self.assertIsNotNone(penalty.disputed_at)
        self.assertEqual(penalty.resolved_by, self.admin)
        self.assertTrue(
            Notification.objects.filter(recipient=self.citizen, title__icontains="Dispute rejected").exists()
        )

    def test_reject_dispute_requires_future_due_date(self):
        penalty = self.make_penalty(status=Status.DISPUTED, disputed_at=timezone.now())
        self.login("pen_adm1")
        response = self.client.post(
            self.url("reject_dispute", penalty),
            {"reject-note": "Evidence confirms it.",
             "reject-new_due_date": self.days_from_today(-1).isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.DISPUTED)

    def test_cancel_only_works_on_open_penalties(self):
        paid = self.make_penalty(status=Status.PAID)
        open_penalty = self.make_penalty()
        self.login("pen_adm1")
        data = {"cancel-reason": "Issued in error."}

        self.client.post(self.url("cancel", paid), data)
        paid.refresh_from_db()
        self.assertEqual(paid.status, Status.PAID)

        self.client.post(self.url("cancel", open_penalty), data)
        open_penalty.refresh_from_db()
        self.assertEqual(open_penalty.status, Status.CANCELLED)

    def test_super_admin_can_resolve(self):
        penalty = self.make_penalty()
        self.login("pen_sup")
        self.client.post(self.url("waive", penalty), {"waive-reason": "Waived by the commissioner."})
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, Status.WAIVED)


class PenaltyServiceTests(PenaltyBase):
    def test_summary_totals(self):
        self.make_penalty(amount=Decimal("500.00"))
        self.make_penalty(amount=Decimal("300.00"), due_date=self.days_from_today(-3))
        self.make_penalty(amount=Decimal("200.00"), status=Status.DISPUTED)
        self.make_penalty(amount=Decimal("1000.00"), status=Status.PAID)
        self.make_penalty(amount=Decimal("50.00"), status=Status.WAIVED)

        summary = services.summarise_penalties(Penalty.objects.all())
        self.assertEqual(summary["count"], 5)
        self.assertEqual(summary["issued_count"], 2)
        self.assertEqual(summary["disputed_count"], 1)
        self.assertEqual(summary["paid_count"], 1)
        self.assertEqual(summary["overdue_count"], 1)
        self.assertEqual(summary["outstanding"], Decimal("800.00"))
        self.assertEqual(summary["disputed_amount"], Decimal("200.00"))
        self.assertEqual(summary["collected"], Decimal("1000.00"))

    def test_overdue_flag_and_filter(self):
        late = self.make_penalty(due_date=self.days_from_today(-1))
        on_time = self.make_penalty()
        paid_late = self.make_penalty(due_date=self.days_from_today(-1), status=Status.PAID)
        self.assertTrue(late.is_overdue)
        self.assertFalse(on_time.is_overdue)
        self.assertFalse(paid_late.is_overdue)

        self.login("pen_adm1")
        response = self.client.get(reverse("penalties:list"), {"overdue": "1"})
        self.assertEqual({p.pk for p in response.context["page_obj"]}, {late.pk})

    def test_history_records_each_step(self):
        self.login("pen_ho")
        self.client.post(reverse("penalties:create"), self.form_data())
        penalty = Penalty.objects.get()

        self.login("pen_cit1")
        self.client.post(
            self.url("dispute", penalty), {"dispute-reason": "I was out of the city on that day."}
        )

        self.login("pen_adm1")
        self.client.post(
            self.url("reject_dispute", penalty),
            {"reject-note": "Evidence confirms the violation.",
             "reject-new_due_date": self.days_from_today(7).isoformat()},
        )
        self.assertEqual(
            list(penalty.events.values_list("status", flat=True)),
            ["issued", "disputed", "issued"],
        )
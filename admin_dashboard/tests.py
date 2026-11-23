"""Tests for the Municipal Admin review console."""
from django.urls import reverse

from complaints.models import Complaint
from complaints.workflow_fixtures import WorkflowTestCase
from notifications.models import Notification


class AdminConsoleTests(WorkflowTestCase):
    def url(self, name):
        return reverse(f"admin_dashboard:{name}", args=[self.complaint.pk])

    def test_citizen_cannot_open_review_console(self):
        self.login("cit1")
        response = self.client.get(reverse("admin_dashboard:queue"))
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_complaint_in_queue(self):
        self.login("adm1")
        response = self.client.get(reverse("admin_dashboard:queue"))
        self.assertContains(response, "Overflowing bin near market")

    def test_start_review_updates_status_and_notifies_citizen(self):
        self.login("adm1")
        response = self.client.post(self.url("start_review"))
        self.assertRedirects(response, self.url("complaint_detail"))
        self.assertStatus(Complaint.Status.UNDER_REVIEW)
        # One notification for the submission, one for the review.
        self.assertEqual(Notification.objects.filter(recipient=self.citizen).count(), 2)

    def test_start_review_requires_post(self):
        self.login("adm1")
        self.assertEqual(self.client.get(self.url("start_review")).status_code, 405)

    def test_cannot_assign_before_review(self):
        self.login("adm1")
        response = self.client.post(
            self.url("assign"),
            {"assign-worker": self.worker.pk, "assign-priority": "medium", "assign-instructions": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertStatus(Complaint.Status.SUBMITTED)
        self.assertIsNone(self.complaint.assigned_worker)

    def test_assign_worker_notifies_worker(self):
        self.to_under_review()
        self.login("adm1")
        self.client.post(
            self.url("assign"),
            {"assign-worker": self.worker.pk, "assign-priority": "high", "assign-instructions": "Bring gloves"},
        )
        self.assertStatus(Complaint.Status.ASSIGNED)
        self.assertEqual(self.complaint.assigned_worker, self.worker)
        self.assertEqual(self.complaint.priority, "high")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.worker, category=Notification.Category.TASK
            ).exists()
        )

    def test_cannot_assign_a_non_worker(self):
        self.to_under_review()
        self.login("adm1")
        response = self.client.post(
            self.url("assign"),
            {"assign-worker": self.citizen.pk, "assign-priority": "medium", "assign-instructions": ""},
        )
        self.assertEqual(response.status_code, 200)  # form re-rendered with an error
        self.assertStatus(Complaint.Status.UNDER_REVIEW)

    def test_reject_requires_reason(self):
        self.login("adm1")
        response = self.client.post(self.url("reject"), {"reject-reason": ""})
        self.assertEqual(response.status_code, 200)
        self.assertStatus(Complaint.Status.SUBMITTED)

    def test_reject_with_reason_notifies_citizen(self):
        self.login("adm1")
        self.client.post(self.url("reject"), {"reject-reason": "Duplicate of an earlier report"})
        self.assertStatus(Complaint.Status.REJECTED)
        self.assertTrue(
            Notification.objects.filter(recipient=self.citizen, message__icontains="Duplicate").exists()
        )

    def test_worker_overview_lists_workers(self):
        self.login("adm1")
        response = self.client.get(reverse("admin_dashboard:workers"))
        self.assertContains(response, "wrk1")
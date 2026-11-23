"""Tests for worker tasks and the full complaint workflow."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from complaints.models import Complaint
from complaints.workflow_fixtures import WorkflowTestCase, make_image
from notifications.models import Notification

NOTE = "Waste collected and area cleaned."


class WorkerBase(WorkflowTestCase):
    def worker_url(self, name):
        return reverse(f"worker:{name}", args=[self.complaint.pk])

    def admin_url(self, name):
        return reverse(f"admin_dashboard:{name}", args=[self.complaint.pk])


class WorkerTaskTests(WorkerBase):
    def test_worker_sees_only_own_tasks(self):
        self.to_assigned()
        self.login("wrk2")
        self.assertNotContains(self.client.get(reverse("worker:task_list")), "Overflowing bin near market")
        self.login("wrk1")
        self.assertContains(self.client.get(reverse("worker:task_list")), "Overflowing bin near market")

    def test_other_worker_cannot_open_task(self):
        self.to_assigned()
        self.login("wrk2")
        self.assertEqual(self.client.get(self.worker_url("task_detail")).status_code, 404)

    def test_citizen_cannot_open_task_list(self):
        self.login("cit1")
        self.assertEqual(self.client.get(reverse("worker:task_list")).status_code, 403)

    def test_accept_assignment(self):
        self.to_assigned()
        self.login("wrk1")
        response = self.client.post(self.worker_url("task_accept"))
        self.assertRedirects(response, self.worker_url("task_detail"))
        self.assertStatus(Complaint.Status.ACCEPTED)
        self.assertIsNotNone(self.complaint.accepted_at)
        self.assertTrue(Notification.objects.filter(recipient=self.admin, title__icontains="accepted").exists())

    def test_other_worker_cannot_accept(self):
        self.to_assigned()
        self.login("wrk2")
        self.assertEqual(self.client.post(self.worker_url("task_accept")).status_code, 404)
        self.assertStatus(Complaint.Status.ASSIGNED)

    def test_cannot_complete_before_accepting(self):
        self.to_assigned()
        self.login("wrk1")
        self.client.post(self.worker_url("task_complete"), {"completion_note": NOTE, "proof_image": make_image()})
        self.assertStatus(Complaint.Status.ASSIGNED)

    def test_complete_requires_proof_image(self):
        self.to_accepted()
        self.login("wrk1")
        response = self.client.post(self.worker_url("task_complete"), {"completion_note": NOTE})
        self.assertEqual(response.status_code, 200)
        self.assertStatus(Complaint.Status.ACCEPTED)

    def test_non_image_proof_is_rejected(self):
        self.to_accepted()
        self.login("wrk1")
        bad_file = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(self.worker_url("task_complete"), {"completion_note": NOTE, "proof_image": bad_file})
        self.assertEqual(response.status_code, 200)
        self.assertStatus(Complaint.Status.ACCEPTED)

    def test_complete_with_proof_notifies_admin(self):
        self.to_accepted()
        self.login("wrk1")
        self.client.post(self.worker_url("task_complete"), {"completion_note": NOTE, "proof_image": make_image()})
        self.assertStatus(Complaint.Status.COMPLETED)
        self.assertTrue(self.complaint.proof_image.name.startswith("proofs/"))
        self.assertTrue(Notification.objects.filter(recipient=self.admin, title__icontains="Verify").exists())


class FullWorkflowTests(WorkerBase):
    def test_complete_workflow_from_complaint_to_resolution(self):
        # 1. Admin reviews and assigns.
        self.login("adm1")
        self.client.post(self.admin_url("start_review"))
        self.assertStatus(Complaint.Status.UNDER_REVIEW)
        self.client.post(
            self.admin_url("assign"),
            {"assign-worker": self.worker.pk, "assign-priority": "medium", "assign-instructions": ""},
        )
        self.assertStatus(Complaint.Status.ASSIGNED)

        # 2. Worker accepts and completes with proof.
        self.login("wrk1")
        self.client.post(self.worker_url("task_accept"))
        self.assertStatus(Complaint.Status.ACCEPTED)
        self.client.post(self.worker_url("task_complete"), {"completion_note": NOTE, "proof_image": make_image()})
        self.assertStatus(Complaint.Status.COMPLETED)

        # 3. Admin verifies.
        self.login("adm1")
        self.client.post(self.admin_url("verify"), {"verify-note": "Checked the photo."})
        self.assertStatus(Complaint.Status.RESOLVED)
        self.assertIsNotNone(self.complaint.resolved_at)

        # 4. The citizen was notified and the timeline is complete.
        self.assertTrue(Notification.objects.filter(recipient=self.citizen, title__icontains="resolved").exists())
        self.assertEqual(
            list(self.complaint.history.values_list("status", flat=True)),
            ["submitted", "under_review", "assigned", "accepted", "completed", "resolved"],
        )

    def test_rework_sends_task_back_to_worker(self):
        self.to_completed()
        self.login("adm1")
        self.client.post(self.admin_url("rework"), {"rework-reason": "The photo does not show the cleaned area"})
        self.assertStatus(Complaint.Status.ACCEPTED)
        self.assertIsNone(self.complaint.completed_at)
        self.assertTrue(Notification.objects.filter(recipient=self.worker, title__icontains="more work").exists())

    def test_cannot_verify_before_completion(self):
        self.to_accepted()
        self.login("adm1")
        self.client.post(self.admin_url("verify"), {"verify-note": ""})
        self.assertStatus(Complaint.Status.ACCEPTED)
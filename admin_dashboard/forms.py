"""Forms for the Municipal Admin review console."""
from django import forms
from django.db.models import Count, Q

from accounts.forms import BootstrapFormMixin
from accounts.models import User
from complaints.models import Complaint


class WorkerChoiceField(forms.ModelChoiceField):
    """Shows each worker with their current number of active tasks."""

    def label_from_instance(self, obj):
        return f"{obj.display_name} ({obj.active_tasks} active task(s))"


class AssignWorkerForm(BootstrapFormMixin, forms.Form):
    """Assign (or reassign) a worker to a complaint."""

    worker = WorkerChoiceField(queryset=User.objects.none(), empty_label="Select a worker")
    priority = forms.ChoiceField(choices=Complaint.Priority.choices, initial=Complaint.Priority.MEDIUM)
    instructions = forms.CharField(
        label="Instructions for the worker",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional notes for the worker"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active workers can be chosen.
        self.fields["worker"].queryset = (
            User.objects.filter(role=User.Role.WORKER, is_active=True)
            .annotate(
                active_tasks=Count(
                    "assigned_complaints",
                    filter=Q(
                        assigned_complaints__status__in=(
                            Complaint.Status.ASSIGNED,
                            Complaint.Status.ACCEPTED,
                        )
                    ),
                )
            )
            .order_by("first_name", "username")
        )


class ReasonForm(BootstrapFormMixin, forms.Form):
    """A required reason (used to reject a complaint or send work back)."""

    reason = forms.CharField(
        label="Reason",
        min_length=5,
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Explain why (at least 5 characters)"}),
    )


class VerifyForm(BootstrapFormMixin, forms.Form):
    """Optional note when verifying completed work."""

    note = forms.CharField(label="Verification note (optional)", required=False, max_length=200)
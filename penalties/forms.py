"""Forms for the penalties app."""
from datetime import timedelta

from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin
from accounts.models import User
from inspections.models import Inspection
from waste_management.models import Ward

from .models import Penalty
from .services import RECIPIENT_ROLES

DATE_WIDGET_FORMAT = "%Y-%m-%d"


class IssuePenaltyForm(BootstrapFormMixin, forms.ModelForm):
    """Issue a penalty to a citizen or a bulk waste generator."""

    class Meta:
        model = Penalty
        fields = ("issued_to", "ward", "inspection", "violation_type", "description", "amount", "due_date")
        labels = {"issued_to": "Issue to", "inspection": "Linked inspection"}
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 3, "minlength": 10, "placeholder": "What happened? (at least 10 characters)"}
            ),
            "amount": forms.NumberInput(attrs={"min": "1", "max": "100000", "step": "0.01"}),
            "due_date": forms.DateInput(format=DATE_WIDGET_FORMAT, attrs={"type": "date"}),
        }
        help_texts = {"inspection": "Optional. Inspections from the last 180 days."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["issued_to"].queryset = User.objects.filter(
            role__in=RECIPIENT_ROLES, is_active=True
        ).order_by("first_name", "username")
        self.fields["issued_to"].empty_label = "Select a person"
        self.fields["issued_to"].label_from_instance = (
            lambda user: f"{user.display_name} (@{user.username}) – {user.get_role_display()}"
        )

        self.fields["ward"].queryset = Ward.objects.filter(is_active=True)
        self.fields["ward"].empty_label = "Select ward"

        recent = timezone.localdate() - timedelta(days=180)
        self.fields["inspection"].queryset = Inspection.objects.filter(
            inspection_date__gte=recent
        ).select_related("ward")
        self.fields["inspection"].empty_label = "Not linked to an inspection"
        self.fields["inspection"].label_from_instance = (
            lambda i: f"{i.reference} – {i.premises_name} ({i.inspection_date:%d %b %Y})"
        )

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 10:
            raise forms.ValidationError("Describe the violation in at least 10 characters.")
        return description

    def clean_due_date(self):
        due_date = self.cleaned_data["due_date"]
        if due_date < timezone.localdate():
            raise forms.ValidationError("The due date cannot be in the past.")
        return due_date

    def clean(self):
        cleaned = super().clean()
        inspection = cleaned.get("inspection")
        ward = cleaned.get("ward")
        recipient = cleaned.get("issued_to")
        if inspection:
            if ward and inspection.ward_id != ward.pk:
                self.add_error("ward", "The ward must match the ward of the linked inspection.")
            if recipient and inspection.bulk_generator_id and inspection.bulk_generator_id != recipient.pk:
                self.add_error(
                    "issued_to", "This inspection was of another generator's premises. Choose that generator."
                )
        return cleaned


class DisputeForm(BootstrapFormMixin, forms.Form):
    """The person penalised explains why they dispute it."""

    reason = forms.CharField(
        label="Why are you disputing this penalty?",
        min_length=10, max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "At least 10 characters"}),
    )


class PaymentForm(BootstrapFormMixin, forms.Form):
    """The municipal office records a payment that was received."""

    reference = forms.CharField(
        label="Receipt / reference number", min_length=3, max_length=60,
        widget=forms.TextInput(attrs={"placeholder": "e.g. RCPT-1001"}),
    )


class ReasonForm(BootstrapFormMixin, forms.Form):
    """A required reason (used to waive or cancel a penalty)."""

    reason = forms.CharField(
        label="Reason", min_length=5, max_length=200,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "At least 5 characters"}),
    )


class RejectDisputeForm(BootstrapFormMixin, forms.Form):
    """Reject a dispute: the penalty stands, with a new due date."""

    note = forms.CharField(
        label="Reason for rejecting", min_length=5, max_length=200,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "At least 5 characters"}),
    )
    new_due_date = forms.DateField(
        label="New due date",
        widget=forms.DateInput(format=DATE_WIDGET_FORMAT, attrs={"type": "date"}),
    )

    def clean_new_due_date(self):
        due_date = self.cleaned_data["new_due_date"]
        if due_date < timezone.localdate():
            raise forms.ValidationError("The new due date cannot be in the past.")
        return due_date
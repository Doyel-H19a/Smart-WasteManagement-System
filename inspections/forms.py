"""Forms for the inspections app."""
from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin
from accounts.models import User
from waste_management.models import Ward

from .models import Inspection

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
DATE_WIDGET_FORMAT = "%Y-%m-%d"


class InspectionForm(BootstrapFormMixin, forms.ModelForm):
    """A Health Officer records an inspection."""

    class Meta:
        model = Inspection
        fields = (
            "category", "ward", "premises_name", "address", "bulk_generator", "inspection_date",
            "segregation_rating", "cleanliness_rating", "bin_condition_rating", "outcome",
            "findings", "recommendations", "follow_up_required", "follow_up_date",
            "photo", "latitude", "longitude",
        )
        widgets = {
            "premises_name": forms.TextInput(attrs={"minlength": 3, "placeholder": "e.g. Market lane bins"}),
            "address": forms.TextInput(attrs={"placeholder": "Street, landmark, area"}),
            "inspection_date": forms.DateInput(format=DATE_WIDGET_FORMAT, attrs={"type": "date"}),
            "follow_up_date": forms.DateInput(format=DATE_WIDGET_FORMAT, attrs={"type": "date"}),
            "segregation_rating": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "cleanliness_rating": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "bin_condition_rating": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "findings": forms.Textarea(
                attrs={"rows": 4, "minlength": 10, "placeholder": "What did you observe? (at least 10 characters)"}
            ),
            "recommendations": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional"}),
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
            "latitude": forms.NumberInput(attrs={"min": -90, "max": 90, "placeholder": "Optional"}),
            "longitude": forms.NumberInput(attrs={"min": -180, "max": 180, "placeholder": "Optional"}),
        }
        help_texts = {
            "bulk_generator": "Only for bulk-premises inspections.",
            "photo": "Optional. JPG or PNG, up to 5 MB.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ward"].queryset = Ward.objects.filter(is_active=True)
        self.fields["ward"].empty_label = "Select ward"

        self.fields["bulk_generator"].queryset = User.objects.filter(
            role=User.Role.BULK_GENERATOR, is_active=True
        ).order_by("first_name", "username")
        self.fields["bulk_generator"].empty_label = "Not applicable"
        self.fields["bulk_generator"].label_from_instance = (
            lambda user: f"{user.display_name} (@{user.username})"
        )

    def clean_premises_name(self):
        name = self.cleaned_data["premises_name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Enter at least 3 characters.")
        return name

    def clean_findings(self):
        findings = self.cleaned_data["findings"].strip()
        if len(findings) < 10:
            raise forms.ValidationError("Describe the findings in at least 10 characters.")
        return findings

    def clean_inspection_date(self):
        date = self.cleaned_data["inspection_date"]
        if date > timezone.localdate():
            raise forms.ValidationError("The inspection date cannot be in the future.")
        return date

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        # Only freshly uploaded files have a content_type.
        if photo and hasattr(photo, "content_type"):
            if photo.size > MAX_IMAGE_SIZE:
                raise forms.ValidationError("Image must be 5 MB or smaller.")
            if not photo.content_type.startswith("image/"):
                raise forms.ValidationError("Please upload a valid image file.")
        return photo

    def clean(self):
        cleaned = super().clean()

        category = cleaned.get("category")
        generator = cleaned.get("bulk_generator")
        if category == Inspection.Category.BULK_PREMISES and not generator:
            self.add_error("bulk_generator", "Select the registered generator for a bulk-premises inspection.")
        elif category and category != Inspection.Category.BULK_PREMISES and generator:
            self.add_error("bulk_generator", "Only select a generator for bulk-premises inspections.")

        lat, lon = cleaned.get("latitude"), cleaned.get("longitude")
        if (lat is None) != (lon is None):
            raise forms.ValidationError("Provide both latitude and longitude, or leave both empty.")

        inspection_date = cleaned.get("inspection_date")
        follow_up_date = cleaned.get("follow_up_date")
        if cleaned.get("follow_up_required"):
            if not follow_up_date:
                self.add_error("follow_up_date", "Enter the follow-up date.")
            elif inspection_date and follow_up_date < inspection_date:
                self.add_error("follow_up_date", "The follow-up cannot be before the inspection date.")
        else:
            cleaned["follow_up_date"] = None  # ignore a stray date when no follow-up is needed
        return cleaned
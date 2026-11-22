"""Forms for the complaints app."""
from django import forms

from accounts.forms import BootstrapFormMixin
from waste_management.models import Ward

from .models import Complaint

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


class ComplaintForm(BootstrapFormMixin, forms.ModelForm):
    """Citizen complaint submission form."""

    class Meta:
        model = Complaint
        fields = (
            "title", "category", "ward", "description",
            "address", "latitude", "longitude", "image",
        )
        widgets = {
            "title": forms.TextInput(attrs={"minlength": 5, "placeholder": "Short summary of the problem"}),
            "description": forms.Textarea(
                attrs={"rows": 4, "minlength": 20, "placeholder": "Describe the problem (at least 20 characters)"}
            ),
            "address": forms.TextInput(attrs={"placeholder": "Street, landmark, area"}),
            "latitude": forms.NumberInput(attrs={"min": -90, "max": 90, "placeholder": "Optional"}),
            "longitude": forms.NumberInput(attrs={"min": -180, "max": 180, "placeholder": "Optional"}),
            "image": forms.FileInput(attrs={"accept": "image/*"}),
        }
        help_texts = {"image": "Optional. JPG or PNG, up to 5 MB."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active wards can be chosen.
        self.fields["ward"].queryset = Ward.objects.filter(is_active=True)
        self.fields["ward"].empty_label = "Select your ward"

    def clean_title(self):
        title = self.cleaned_data["title"]
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters long.")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"]
        if len(description) < 20:
            raise forms.ValidationError("Please describe the problem in at least 20 characters.")
        return description

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "content_type"):
            if image.size > MAX_IMAGE_SIZE:
                raise forms.ValidationError("Image must be 5 MB or smaller.")
            if not image.content_type.startswith("image/"):
                raise forms.ValidationError("Please upload a valid image file.")
        return image

    def clean(self):
        cleaned = super().clean()
        lat, lon = cleaned.get("latitude"), cleaned.get("longitude")
        if (lat is None) != (lon is None):
            raise forms.ValidationError("Provide both latitude and longitude, or leave both empty.")
        return cleaned
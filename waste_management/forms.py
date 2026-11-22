"""Forms for the waste_management app."""
from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Ward


class WardForm(BootstrapFormMixin, forms.ModelForm):
    """Create or edit a ward."""

    class Meta:
        model = Ward
        fields = ("ward_number", "name", "zone", "population", "latitude", "longitude", "is_active")
        widgets = {
            "latitude": forms.NumberInput(attrs={"min": -90, "max": 90}),
            "longitude": forms.NumberInput(attrs={"min": -180, "max": 180}),
        }

    def clean(self):
        cleaned = super().clean()
        lat, lon = cleaned.get("latitude"), cleaned.get("longitude")
        if (lat is None) != (lon is None):
            raise forms.ValidationError("Provide both latitude and longitude, or leave both empty.")
        return cleaned
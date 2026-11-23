"""Forms for the AI classification app."""
from django import forms

from accounts.forms import BootstrapFormMixin

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


class ClassifyForm(BootstrapFormMixin, forms.Form):
    """Upload one image to classify."""

    image = forms.ImageField(
        label="Waste photo",
        widget=forms.FileInput(attrs={"accept": "image/*"}),
        help_text="JPG or PNG, up to 5 MB.",
    )

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > MAX_IMAGE_SIZE:
            raise forms.ValidationError("Image must be 5 MB or smaller.")
        return image
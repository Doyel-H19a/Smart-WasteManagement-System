"""Forms for the worker app."""
from django import forms

from accounts.forms import BootstrapFormMixin

MAX_PROOF_SIZE = 5 * 1024 * 1024  # 5 MB


class CompleteTaskForm(BootstrapFormMixin, forms.Form):
    """Completion report: a note and a required proof photo."""

    completion_note = forms.CharField(
        label="What was done?",
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "Describe the work done (at least 10 characters)"}
        ),
    )
    proof_image = forms.ImageField(
        label="Proof photo",
        widget=forms.FileInput(attrs={"accept": "image/*"}),
        help_text="Required. JPG or PNG, up to 5 MB.",
    )

    def clean_proof_image(self):
        image = self.cleaned_data["proof_image"]
        if image.size > MAX_PROOF_SIZE:
            raise forms.ValidationError("Image must be 5 MB or smaller.")
        return image
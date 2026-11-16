"""Forms for the accounts app."""
from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)

from .models import User

MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB

# Only these roles may be chosen on the public registration page.
SELF_REGISTER_ROLES = [
    User.Role.CITIZEN,
    User.Role.GREEN_CHAMPION,
    User.Role.BULK_GENERATOR,
]


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to widgets and flags invalid fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css}".strip()

    def full_clean(self):
        super().full_clean()
        if self.is_bound and self._errors:
            for name in self._errors:
                if name in self.fields:
                    css = self.fields[name].widget.attrs.get("class", "")
                    self.fields[name].widget.attrs["class"] = f"{css} is-invalid".strip()


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Public registration form (Citizen, Green Champion, Bulk Waste Generator)."""

    role = forms.ChoiceField(
        label="Register as",
        choices=[(r.value, r.label) for r in SELF_REGISTER_ROLES],
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone_number", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone_number"].widget.attrs.update(
            {
                "pattern": r"\+?[0-9]{10,15}",
                "placeholder": "e.g. 9876543210",
                "title": "10-15 digits, optional leading +",
            }
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """Login form styled with Bootstrap."""


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    """Lets a user edit their own profile (role is NOT editable here)."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "address", "profile_image")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "profile_image": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].widget.attrs.update(
            {"pattern": r"\+?[0-9]{10,15}", "title": "10-15 digits, optional leading +"}
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def clean_profile_image(self):
        image = self.cleaned_data.get("profile_image")
        # Only validate freshly uploaded files (they have a content_type).
        if image and hasattr(image, "content_type"):
            if image.size > MAX_IMAGE_SIZE:
                raise forms.ValidationError("Image must be 2 MB or smaller.")
            if not image.content_type.startswith("image/"):
                raise forms.ValidationError("Please upload a valid image file.")
        return image


class AdminUserCreationForm(UserCreationForm):
    """Used by the Django admin 'Add user' page with the custom model."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")


class AdminUserChangeForm(UserChangeForm):
    """Used by the Django admin 'Change user' page with the custom model."""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
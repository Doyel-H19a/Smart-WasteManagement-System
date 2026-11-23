"""Forms for the waste_management app."""
from django import forms
from django.db.models import Q

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import CollectionSchedule, Ward, WasteMovement


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


class CollectionScheduleForm(BootstrapFormMixin, forms.ModelForm):
    """Create or edit a weekly collection schedule (Municipal Admin and Super Admin)."""

    class Meta:
        model = CollectionSchedule
        fields = (
            "ward", "route_name", "waste_type", "weekday", "start_time", "end_time",
            "assigned_worker", "vehicle_number", "notes", "is_active",
        )
        widgets = {
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "end_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "route_name": forms.TextInput(attrs={"minlength": 3, "placeholder": "e.g. Main Road and market lane"}),
            "vehicle_number": forms.TextInput(attrs={"placeholder": "Optional"}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional"}),
        }
        help_texts = {"assigned_worker": "Optional. The worker is notified when assigned."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_ward = self.instance.ward_id
        current_worker = self.instance.assigned_worker_id

        # Active wards only (an existing inactive ward stays selectable when editing).
        self.fields["ward"].queryset = Ward.objects.filter(Q(is_active=True) | Q(pk=current_ward))
        self.fields["ward"].empty_label = "Select a ward"

        # Active workers only (the current worker stays selectable when editing).
        self.fields["assigned_worker"].queryset = User.objects.filter(
            Q(role=User.Role.WORKER, is_active=True) | Q(role=User.Role.WORKER, pk=current_worker)
        ).order_by("first_name", "username")
        self.fields["assigned_worker"].empty_label = "Unassigned"
        self.fields["assigned_worker"].label_from_instance = (
            lambda user: f"{user.display_name} (@{user.username})"
        )

    def clean_route_name(self):
        route = self.cleaned_data["route_name"].strip()
        if len(route) < 3:
            raise forms.ValidationError("Route name must be at least 3 characters long.")
        return route


class WasteMovementForm(BootstrapFormMixin, forms.ModelForm):
    """A worker logs a pickup, transfer or disposal."""

    class Meta:
        model = WasteMovement
        fields = (
            "movement_type", "waste_type", "quantity_kg", "ward", "schedule",
            "from_location", "to_location", "vehicle_number", "latitude", "longitude", "notes",
        )
        widgets = {
            "quantity_kg": forms.NumberInput(attrs={"min": "0.01", "placeholder": "e.g. 250.50"}),
            "from_location": forms.TextInput(attrs={"placeholder": "e.g. Market collection point"}),
            "to_location": forms.TextInput(attrs={"placeholder": "e.g. Transfer station"}),
            "vehicle_number": forms.TextInput(attrs={"placeholder": "Optional"}),
            "latitude": forms.NumberInput(attrs={"min": -90, "max": 90, "placeholder": "Optional"}),
            "longitude": forms.NumberInput(attrs={"min": -180, "max": 180, "placeholder": "Optional"}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional"}),
        }

    def __init__(self, *args, worker, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker = worker

        self.fields["ward"].queryset = Ward.objects.filter(is_active=True)
        self.fields["ward"].empty_label = "Select ward"

        # A worker can only link their own active schedules.
        self.fields["schedule"].queryset = CollectionSchedule.objects.filter(
            assigned_worker=worker, is_active=True
        ).select_related("ward")
        self.fields["schedule"].empty_label = "Not linked to a schedule"
        self.fields["schedule"].label_from_instance = (
            lambda s: f"{s.get_weekday_display()} {s.time_window} – {s.route_name} ({s.ward})"
        )

    def clean(self):
        cleaned = super().clean()
        lat, lon = cleaned.get("latitude"), cleaned.get("longitude")
        if (lat is None) != (lon is None):
            raise forms.ValidationError("Provide both latitude and longitude, or leave both empty.")

        schedule, ward = cleaned.get("schedule"), cleaned.get("ward")
        if schedule and ward and schedule.ward_id != ward.pk:
            self.add_error("ward", "The ward must match the ward of the selected schedule.")
        return cleaned
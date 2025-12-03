from django import forms

from .models import Business, Service, StaffMember, WorkingHours
from .timezones import timezone_choices


class BusinessForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=timezone_choices,
        help_text="Times on your booking page and in emails use this time zone.",
    )

    class Meta:
        model = Business
        fields = [
            "name",
            "slug",
            "timezone",
            "email",
            "phone",
            "address",
            "description",
            "slot_interval_minutes",
            "min_notice_minutes",
            "max_advance_days",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "min_notice_minutes": "Minimum notice (minutes)",
            "max_advance_days": "Book up to (days ahead)",
        }

    def clean_slug(self):
        return self.cleaned_data["slug"].lower()


class BusinessSetupForm(BusinessForm):
    class Meta(BusinessForm.Meta):
        fields = ["name", "slug", "timezone", "email"]


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "duration_minutes",
            "price",
            "buffer_before_minutes",
            "buffer_after_minutes",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class StaffForm(forms.ModelForm):
    class Meta:
        model = StaffMember
        fields = [
            "name",
            "email",
            "services",
        ]
        widgets = {
            "services": forms.CheckboxSelectMultiple,
        }
        help_texts = {
            "email": "Optional. Used to send staff a copy of their bookings.",
            "services": "The services this person can be booked for.",
        }

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["services"].queryset = business.services.filter(is_active=True)


SHIFTS_PER_DAY = 2


class WeeklyHoursForm(forms.Form):
    """Working hours for a whole week: up to two shifts per weekday.

    Field names look like ``d0_1_start`` (Monday, first shift, start time).
    """

    def __init__(self, *args, staff, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff = staff
        if not self.is_bound:
            self.initial.update(self._initial_from(staff))
        for weekday in range(7):
            for shift in range(1, SHIFTS_PER_DAY + 1):
                for part in ("start", "end"):
                    self.fields[f"d{weekday}_{shift}_{part}"] = forms.TimeField(
                        required=False,
                        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                    )

    @staticmethod
    def _initial_from(staff):
        initial = {}
        counts = {}
        for row in staff.working_hours.all():
            counts[row.weekday] = counts.get(row.weekday, 0) + 1
            shift = counts[row.weekday]
            if shift > SHIFTS_PER_DAY:
                continue
            initial[f"d{row.weekday}_{shift}_start"] = row.start_time
            initial[f"d{row.weekday}_{shift}_end"] = row.end_time
        return initial

    def days(self):
        """Rows for the template: one per weekday with its bound fields."""
        rows = []
        for weekday, label in WorkingHours.Weekday.choices:
            shifts = [
                (self[f"d{weekday}_{shift}_start"], self[f"d{weekday}_{shift}_end"])
                for shift in range(1, SHIFTS_PER_DAY + 1)
            ]
            rows.append({"weekday": weekday, "label": label, "shifts": shifts})
        return rows

    def clean(self):
        cleaned = super().clean()
        self.shifts = []
        for weekday in range(7):
            previous_end = None
            for shift in range(1, SHIFTS_PER_DAY + 1):
                start_name, end_name = f"d{weekday}_{shift}_start", f"d{weekday}_{shift}_end"
                start, end = cleaned.get(start_name), cleaned.get(end_name)
                if start is None and end is None:
                    continue
                if start is None or end is None:
                    self.add_error(start_name if start is None else end_name, "Enter both times.")
                    continue
                if end <= start:
                    self.add_error(end_name, "Must be after the start time.")
                    continue
                if previous_end is not None and start < previous_end:
                    self.add_error(start_name, "Overlaps the shift before it.")
                    continue
                previous_end = end
                self.shifts.append((weekday, start, end))
        return cleaned

    def save(self):
        self.staff.working_hours.all().delete()
        WorkingHours.objects.bulk_create(
            WorkingHours(staff=self.staff, weekday=weekday, start_time=start, end_time=end)
            for weekday, start, end in self.shifts
        )

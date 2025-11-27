from django import forms

from .models import Business
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

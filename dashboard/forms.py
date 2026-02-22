from datetime import datetime

from django import forms

from appointments.forms import clean_phone_number
from scheduling.availability import bookable_staff


class ManualBookingForm(forms.Form):
    """A booking the business adds itself, for a phone call or a walk-in."""

    service = forms.ModelChoiceField(queryset=None)
    staff = forms.ModelChoiceField(queryset=None, label="With")
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    customer_name = forms.CharField(max_length=120, label="Customer name")
    customer_email = forms.EmailField(
        label="Customer email", help_text="They get the confirmation and the booking link."
    )
    customer_phone = forms.CharField(max_length=32, label="Customer phone")

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.business = business
        self.fields["service"].queryset = business.services.filter(is_active=True)
        self.fields["staff"].queryset = business.staff.all()

    def clean_customer_phone(self):
        return clean_phone_number(self.cleaned_data["customer_phone"])

    def clean(self):
        cleaned = super().clean()
        service, staff = cleaned.get("service"), cleaned.get("staff")
        if service and staff and not bookable_staff(service).filter(pk=staff.pk).exists():
            self.add_error("staff", f"{staff.name} doesn't offer {service.name}.")
        if cleaned.get("date") and cleaned.get("time"):
            cleaned["start"] = datetime.combine(
                cleaned["date"], cleaned["time"], tzinfo=self.business.tz
            )
        return cleaned

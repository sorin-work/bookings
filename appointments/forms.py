import re

from django import forms

from .services import Customer

PHONE_RE = re.compile(r"^\d{7,15}$")


def clean_phone_number(value):
    phone = value.strip()
    if not PHONE_RE.match(phone):
        raise forms.ValidationError("Enter a phone number we can call.")
    return phone


class CustomerForm(forms.Form):
    name = forms.CharField(max_length=120, label="Your name")
    email = forms.EmailField(label="Email", help_text="We'll send the confirmation here.")
    phone = forms.CharField(max_length=32, label="Phone")

    def clean_name(self):
        # Collapse line breaks and runs of spaces; names end up in email subjects.
        return " ".join(self.cleaned_data["name"].split())

    def clean_email(self):
        return self.cleaned_data["email"].strip()

    def clean_phone(self):
        return clean_phone_number(self.cleaned_data["phone"])

    def customer(self):
        data = self.cleaned_data
        return Customer(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
        )

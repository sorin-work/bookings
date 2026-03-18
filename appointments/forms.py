import re

from django import forms

from .services import Customer

# Digits with the usual separators people type: +44 7700 900123, (555) 010-0199.
PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,25}$")


def clean_phone_number(value):
    phone = value.strip()
    if not PHONE_RE.match(phone):
        raise forms.ValidationError("Enter a phone number we can call.")
    digits = sum(ch.isdigit() for ch in phone)
    if not 7 <= digits <= 15:
        raise forms.ValidationError("Enter a phone number we can call.")
    return phone


class CustomerForm(forms.Form):
    name = forms.CharField(max_length=120, label="Your name")
    email = forms.EmailField(label="Email", help_text="We'll send the confirmation here.")
    phone = forms.CharField(max_length=32, label="Phone")
    note = forms.CharField(
        required=False,
        max_length=1000,
        label="Anything we should know? (optional)",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    # Hidden from people with CSS; bots that fill in every field give themselves away.
    website = forms.CharField(required=False, label="Leave this empty")

    def clean_name(self):
        # Collapse line breaks and runs of spaces; names end up in email subjects.
        return " ".join(self.cleaned_data["name"].split())

    def clean_email(self):
        return self.cleaned_data["email"].strip()

    def clean_phone(self):
        return clean_phone_number(self.cleaned_data["phone"])

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Please leave this field empty.")
        return ""

    def customer(self):
        data = self.cleaned_data
        return Customer(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            note=data.get("note", ""),
        )

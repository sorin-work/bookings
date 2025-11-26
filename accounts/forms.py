from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction

from businesses.models import Business
from businesses.timezones import timezone_choices
from businesses.utils import unique_slug

from .models import User


class SignupForm(BaseUserCreationForm):
    business_name = forms.CharField(
        max_length=120, help_text="Shown to customers on your booking page."
    )
    timezone = forms.ChoiceField(
        choices=timezone_choices,
        initial="Europe/London",
        help_text="Where your business is. Booking times use this time zone.",
    )

    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("There's already an account with this email address.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        Business.objects.create(
            owner=user,
            name=self.cleaned_data["business_name"],
            slug=unique_slug(self.cleaned_data["business_name"]),
            timezone=self.cleaned_data["timezone"],
        )
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"})
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

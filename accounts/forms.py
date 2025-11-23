from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm

from .models import User


class SignupForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("There's already an account with this email address.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"})
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

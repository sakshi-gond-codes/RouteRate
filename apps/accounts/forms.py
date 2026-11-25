from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password

from apps.core.forms import BootstrapFormMixin

from .models import User


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class UserForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="At least 8 characters. Leave blank to keep the current password.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "is_active"]
        help_texts = {"username": "Used to log in.", "is_active": "Inactive users cannot log in."}

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        if not self.instance.pk:
            self.fields["password"].required = True
            self.fields["password"].help_text = "At least 8 characters."

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password, self.instance if self.instance.pk else None)
        return password

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.current_user and self.instance.pk == self.current_user.pk:
            if data.get("role") != User.Role.ADMIN or not data.get("is_active"):
                raise forms.ValidationError("You cannot remove your own admin access or deactivate yourself.")
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

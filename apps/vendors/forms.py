from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Vendor


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "code", "contact_name", "contact_email", "default_increment", "priority", "is_active", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

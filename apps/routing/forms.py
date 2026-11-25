from django import forms
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin
from apps.core.models import Country

from .models import BlockedDestination, Customer, LcrRun, MarginRule


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "code", "contact_email", "billing_increment", "notice_days", "rate_decimals",
                  "is_active", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class MarginRuleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MarginRule
        fields = ["name", "customer", "country", "prefix", "kind", "value", "min_margin", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].empty_label = "All customers"
        self.fields["country"].empty_label = "Any country"
        self.fields["country"].queryset = Country.objects.order_by("name")


class BlockedDestinationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BlockedDestination
        fields = ["prefix", "vendor", "reason", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].empty_label = "All vendors (block completely)"


class LcrRunForm(BootstrapFormMixin, forms.Form):
    as_of_date = forms.DateField(widget=forms.DateInput, label="Rates in force on",
                                 help_text="Use a future date to see the effect of scheduled rate changes")
    notes = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["as_of_date"].initial = timezone.localdate()


class RateSheetForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(queryset=Customer.objects.filter(is_active=True))
    lcr_run = forms.ModelChoiceField(queryset=LcrRun.objects.all()[:20], label="Based on LCR run",
                                     help_text="Cost comes from the primary route of this run")
    effective_date = forms.DateField(widget=forms.DateInput,
                                     help_text="Increases are moved out to respect the customer's notice period")
    notes = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["effective_date"].initial = timezone.localdate()
        self.fields["lcr_run"].queryset = LcrRun.objects.order_by("-created_at")
        self.fields["lcr_run"].label_from_instance = (
            lambda r: f"#{r.pk} - rates as of {r.as_of_date} ({r.prefix_count} prefixes, run {r.created_at:%d %b %H:%M})"
        )
        first = LcrRun.objects.order_by("-created_at").first()
        if first:
            self.fields["lcr_run"].initial = first.pk

from django import forms
from django.conf import settings
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin
from apps.vendors.models import Vendor

from .models import RateDeck
from .services.mapping import FIELDS, REQUIRED_FIELDS
from .services.reader import DeckReadError, file_type_from_name


class DeckUploadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RateDeck
        fields = ["vendor", "file", "deck_type", "default_effective_date", "duplicate_policy", "notes"]
        widgets = {
            "deck_type": forms.RadioSelect,
            "default_effective_date": forms.DateInput,
            "notes": forms.TextInput(attrs={"placeholder": "Optional, e.g. 'Weekly A-Z from vendor email'"}),
        }
        labels = {
            "file": "Rate deck file (.csv or .xlsx)",
            "default_effective_date": "Default effective date",
            "duplicate_policy": "If a prefix appears twice with different rates",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(is_active=True).order_by("name")
        self.fields["default_effective_date"].initial = timezone.localdate()
        self.fields["file"].widget.attrs["accept"] = ".csv,.xlsx,.xlsm,.txt"
        self.fields["deck_type"].widget.attrs["class"] = "form-check-input"

    def clean_file(self):
        f = self.cleaned_data["file"]
        max_mb = settings.ROUTERATE["MAX_UPLOAD_MB"]
        if f.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"File is larger than {max_mb} MB.")
        if f.size == 0:
            raise forms.ValidationError("The file is empty.")
        try:
            self.file_type = file_type_from_name(f.name)
        except DeckReadError as exc:
            raise forms.ValidationError(str(exc)) from None
        return f


class MappingForm(BootstrapFormMixin, forms.Form):
    """Column mapping built dynamically from the columns found in the uploaded file."""

    header_row = forms.IntegerField(min_value=1, label="Header row", help_text="Row number of the column titles")
    sheet = forms.ChoiceField(required=False, label="Excel sheet")
    date_order = forms.ChoiceField(
        choices=[("DMY", "Day first (31/12/2026)"), ("MDY", "Month first (12/31/2026)")],
        label="Date format", help_text="ISO dates (2026-12-31) and Excel dates always work",
    )
    save_mapping = forms.BooleanField(required=False, initial=True,
                                      label="Remember this mapping for the vendor's next upload")

    def __init__(self, *args, columns=(), sheets=(), **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "— Not in this file —")] + [(c, c) for c in columns]
        for key, label, required, help_text in FIELDS:
            self.fields[f"map_{key}"] = forms.ChoiceField(
                choices=choices, required=required, label=label, help_text=help_text,
            )
            self.fields[f"map_{key}"].widget.attrs.update({"class": "form-select map-select", "data-field": key})
        if sheets:
            self.fields["sheet"].choices = [(s, s) for s in sheets]
        else:
            del self.fields["sheet"]

    def mapping_fields(self):
        return [self[f"map_{key}"] for key, *_ in FIELDS]

    def clean(self):
        data = super().clean()
        used = {}
        for key, label, *_ in FIELDS:
            col = data.get(f"map_{key}")
            if not col:
                continue
            if col in used:
                raise forms.ValidationError(f"Column '{col}' is mapped to both {used[col]} and {label}.")
            used[col] = label
        for key in REQUIRED_FIELDS:
            if not data.get(f"map_{key}"):
                self.add_error(f"map_{key}", "This column is required.")
        return data

    def columns(self):
        return {key: self.cleaned_data.get(f"map_{key}") or "" for key, *_ in FIELDS
                if self.cleaned_data.get(f"map_{key}")}

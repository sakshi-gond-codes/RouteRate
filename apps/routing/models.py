from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from apps.core.models import Country
from apps.ratedecks.models import ChangeType
from apps.vendors.models import Vendor, increment_validator

prefix_validator = RegexValidator(r"^\d{1,15}$", "Digits only, up to 15 (no + or 00).")


class Customer(models.Model):
    """A customer who buys termination from us and receives rate sheets."""

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="Used in rate sheet references, e.g. HRB")
    contact_email = models.EmailField(blank=True)
    billing_increment = models.CharField(max_length=10, default="60/60", validators=[increment_validator])
    notice_days = models.PositiveSmallIntegerField(
        default=7, validators=[MaxValueValidator(60)],
        help_text="Rate increases on their sheet take effect no sooner than this many days after issue",
    )
    rate_decimals = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(2), MaxValueValidator(6)])
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MarginRule(models.Model):
    """
    How much we add on top of our cost. The most specific matching rule wins:
    customer rules beat global rules, and a prefix rule beats a country rule,
    which beats a default rule. Longer prefixes beat shorter ones.
    """

    class Kind(models.TextChoices):
        PERCENT = "percent", "Percentage markup (%)"
        FIXED = "fixed", "Fixed amount per minute (USD)"

    name = models.CharField(max_length=120)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name="margin_rules",
                                 help_text="Leave empty to apply to all customers")
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.CASCADE,
                                help_text="Apply to one country (optional)")
    prefix = models.CharField(max_length=15, blank=True, validators=[prefix_validator],
                              help_text="Apply to this prefix and everything under it (optional)")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=4,
                                help_text="Percent (e.g. 12.5) or USD per minute (e.g. 0.0020)")
    min_margin = models.DecimalField(max_digits=10, decimal_places=6, default=0,
                                     help_text="Minimum profit per minute in USD, applied after the markup")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["customer__name", "country__name", "prefix", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.country_id and self.prefix:
            raise ValidationError("Choose either a country or a prefix, not both.")
        if self.value is not None and self.value < 0:
            raise ValidationError({"value": "Markup cannot be negative."})
        if self.kind == self.Kind.PERCENT and self.value is not None and self.value > 500:
            raise ValidationError({"value": "Percentage looks too high (max 500%)."})

    @property
    def scope_label(self):
        if self.prefix:
            return f"Prefix {self.prefix}"
        if self.country_id:
            return self.country.name
        return "All destinations"

    @property
    def markup_label(self):
        if self.kind == self.Kind.PERCENT:
            return f"+{self.value.normalize():f}%"
        return f"+${self.value:.4f}/min"


class BlockedDestination(models.Model):
    """
    A prefix we must not route. Without a vendor it is blocked completely (not routed and not sold).
    With a vendor, only that vendor is skipped for the prefix (e.g. poor call quality).
    """

    prefix = models.CharField(max_length=15, validators=[prefix_validator],
                              help_text="Blocks this prefix and every longer prefix under it")
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.CASCADE, related_name="blocks",
                               help_text="Leave empty to block the destination for all vendors")
    reason = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["prefix"]

    def __str__(self):
        target = self.vendor.code if self.vendor_id else "all vendors"
        return f"{self.prefix} ({target})"


class LcrRun(models.Model):
    """A saved Least Cost Routing calculation for a given date."""

    as_of_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=200, blank=True)
    vendor_count = models.PositiveIntegerField(default=0)
    prefix_count = models.PositiveIntegerField(default=0)
    routed_count = models.PositiveIntegerField(default=0)
    single_route_count = models.PositiveIntegerField(default=0)
    no_route_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    avg_primary_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"LCR #{self.pk} as of {self.as_of_date}"


class LcrEntry(models.Model):
    class Status(models.TextChoices):
        ROUTED = "routed", "Primary + backup"
        SINGLE = "single", "No backup"
        NO_ROUTE = "no_route", "No route"
        BLOCKED = "blocked", "Blocked"

    run = models.ForeignKey(LcrRun, on_delete=models.CASCADE, related_name="entries")
    prefix = models.CharField(max_length=15)
    country = models.ForeignKey(Country, null=True, on_delete=models.SET_NULL)
    destination = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices)
    vendor_count = models.PositiveSmallIntegerField(default=0)
    primary_vendor = models.ForeignKey(Vendor, null=True, on_delete=models.SET_NULL, related_name="+")
    primary_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    primary_via = models.CharField(max_length=15, blank=True, help_text="Vendor prefix used when not an exact match")
    backup_vendor = models.ForeignKey(Vendor, null=True, on_delete=models.SET_NULL, related_name="+")
    backup_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    backup_via = models.CharField(max_length=15, blank=True)
    third_vendor = models.ForeignKey(Vendor, null=True, on_delete=models.SET_NULL, related_name="+")
    third_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["prefix"]
        indexes = [models.Index(fields=["run", "prefix"]), models.Index(fields=["run", "status"])]

    @property
    def backup_gap_pct(self):
        """How much more the backup route costs than the primary."""
        if self.primary_rate and self.backup_rate:
            return float((self.backup_rate - self.primary_rate) / self.primary_rate * 100)
        return None


class RateSheet(models.Model):
    """A versioned customer price list generated from an LCR run plus margin rules."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="rate_sheets")
    lcr_run = models.ForeignKey(LcrRun, null=True, on_delete=models.SET_NULL, related_name="rate_sheets")
    version = models.PositiveIntegerField()
    reference = models.CharField(max_length=40, unique=True)
    effective_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    line_count = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    increase_count = models.PositiveIntegerField(default=0)
    decrease_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    removed_count = models.PositiveIntegerField(default=0)
    notice_adjusted_count = models.PositiveIntegerField(default=0)
    avg_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    avg_sell = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    avg_margin_pct = models.DecimalField(max_digits=7, decimal_places=2, null=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("customer", "version")]

    def __str__(self):
        return self.reference


class RateSheetLine(models.Model):
    sheet = models.ForeignKey(RateSheet, on_delete=models.CASCADE, related_name="lines")
    prefix = models.CharField(max_length=15)
    country = models.ForeignKey(Country, null=True, on_delete=models.SET_NULL)
    destination = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=12, decimal_places=6, help_text="Sell rate")
    previous_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    vendor = models.ForeignKey(Vendor, null=True, on_delete=models.SET_NULL, related_name="+")
    backup_vendor = models.ForeignKey(Vendor, null=True, on_delete=models.SET_NULL, related_name="+")
    margin_rule = models.ForeignKey(MarginRule, null=True, on_delete=models.SET_NULL, related_name="+")
    increment = models.CharField(max_length=10)
    effective_date = models.DateField()
    change = models.CharField(max_length=10, choices=ChangeType.choices)
    notice_applied = models.BooleanField(default=False)

    class Meta:
        ordering = ["prefix"]
        indexes = [models.Index(fields=["sheet", "prefix"])]

    @property
    def margin(self):
        return self.rate - self.cost if self.cost is not None else None

    @property
    def margin_pct(self):
        if self.cost:
            return float((self.rate - self.cost) / self.rate * 100) if self.rate else None
        return None

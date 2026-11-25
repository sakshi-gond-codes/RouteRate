from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import Country
from apps.vendors.models import Vendor


class ChangeType(models.TextChoices):
    NEW = "new", "New"
    INCREASE = "increase", "Increase"
    DECREASE = "decrease", "Decrease"
    UNCHANGED = "unchanged", "Unchanged"
    REMOVED = "removed", "Removed"


class ColumnMapping(models.Model):
    """The last column mapping saved for a vendor, re-used on its next upload."""

    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name="column_mapping")
    columns = models.JSONField(default=dict, help_text='e.g. {"prefix": "Dial Code", "rate": "Price"}')
    header_row = models.PositiveIntegerField(default=1)
    sheet_name = models.CharField(max_length=100, blank=True)
    date_order = models.CharField(max_length=3, default="DMY")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mapping for {self.vendor}"


class RateDeck(models.Model):
    """One uploaded vendor rate file and the result of processing it."""

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        VALIDATED = "validated", "Ready to activate"
        ACTIVE = "active", "Active"
        DISCARDED = "discarded", "Discarded"
        FAILED = "failed", "Failed"

    class DeckType(models.TextChoices):
        FULL = "full", "Full A-Z deck (replaces all current rates)"
        PARTIAL = "partial", "Partial update (only the prefixes in the file change)"

    class DuplicatePolicy(models.TextChoices):
        LOWEST = "lowest", "Keep the lowest rate"
        HIGHEST = "highest", "Keep the highest rate"
        LAST = "last", "Keep the last row in the file"
        REJECT = "reject", "Reject all duplicated rows"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="decks")
    file = models.FileField(upload_to="rate_decks/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=5)
    deck_type = models.CharField(max_length=10, choices=DeckType.choices, default=DeckType.FULL)
    default_effective_date = models.DateField(help_text="Used for rows without an effective date")
    effective_date = models.DateField(null=True, blank=True,
                                      help_text="Main effective date of the deck (most common date in the file)")
    duplicate_policy = models.CharField(max_length=10, choices=DuplicatePolicy.choices, default=DuplicatePolicy.LOWEST)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    mapping = models.JSONField(default=dict, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                    related_name="uploaded_decks")
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="activated_decks")

    # Processing statistics
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    prefix_count = models.PositiveIntegerField(default=0)
    expanded_count = models.PositiveIntegerField(default=0, help_text="Extra prefixes created from lists/ranges")
    new_count = models.PositiveIntegerField(default=0)
    increase_count = models.PositiveIntegerField(default=0)
    decrease_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    removed_count = models.PositiveIntegerField(default=0)
    processing_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return f"{self.vendor.code} #{self.pk} {self.original_filename}"

    @property
    def error_rate(self):
        return round(self.error_rows / self.total_rows * 100, 1) if self.total_rows else 0

    @property
    def can_activate(self):
        return self.status == self.Status.VALIDATED and self.prefix_count > 0

    @property
    def can_remap(self):
        return self.status in (self.Status.UPLOADED, self.Status.VALIDATED, self.Status.FAILED)


class RateDeckLine(models.Model):
    """A normalized, validated rate from a deck (one row per prefix)."""

    deck = models.ForeignKey(RateDeck, on_delete=models.CASCADE, related_name="lines")
    row_number = models.PositiveIntegerField()
    prefix = models.CharField(max_length=15)
    country = models.ForeignKey(Country, null=True, on_delete=models.SET_NULL)
    destination = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    increment = models.CharField(max_length=10)
    effective_date = models.DateField()
    change = models.CharField(max_length=10, choices=ChangeType.choices, blank=True)
    previous_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["prefix", "effective_date"]
        indexes = [models.Index(fields=["deck", "prefix"])]


class DeckIssue(models.Model):
    """A problem found while processing a deck. Errors reject the row; warnings keep it."""

    class Level(models.TextChoices):
        ERROR = "error", "Error"
        WARNING = "warning", "Warning"
        DUPLICATE = "duplicate", "Duplicate"

    deck = models.ForeignKey(RateDeck, on_delete=models.CASCADE, related_name="issues")
    row_number = models.PositiveIntegerField(null=True, blank=True)
    level = models.CharField(max_length=10, choices=Level.choices, db_index=True)
    field = models.CharField(max_length=30, blank=True)
    value = models.CharField(max_length=200, blank=True)
    message = models.CharField(max_length=300)

    class Meta:
        ordering = ["row_number", "id"]


class DeckLog(models.Model):
    """Step-by-step processing log shown on the deck page."""

    deck = models.ForeignKey(RateDeck, on_delete=models.CASCADE, related_name="logs")
    level = models.CharField(max_length=10, default="info")  # info, success, warning, error
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class VendorRateQuerySet(models.QuerySet):
    def active_on(self, day):
        """Rates in force on a given date. effective_from is inclusive, effective_to is exclusive."""
        return self.filter(effective_from__lte=day).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=day))

    def scheduled_after(self, day):
        return self.filter(effective_from__gt=day).exclude(effective_to=models.F("effective_from"))


class VendorRate(models.Model):
    """
    The live routing table: one row per vendor, prefix and effective period.

    A newer deck never deletes older rates. It closes them by setting effective_to,
    so the price on any past or future date can always be answered. A row that was
    replaced before it ever started gets effective_to == effective_from (superseded).
    """

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="rates")
    deck = models.ForeignKey(RateDeck, on_delete=models.CASCADE, related_name="live_rates")
    prefix = models.CharField(max_length=15)
    country = models.ForeignKey(Country, null=True, on_delete=models.SET_NULL)
    destination = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    increment = models.CharField(max_length=10, default="60/60")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    change = models.CharField(max_length=10, choices=ChangeType.choices, blank=True)
    previous_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    objects = VendorRateQuerySet.as_manager()

    class Meta:
        ordering = ["prefix", "effective_from"]
        indexes = [
            models.Index(fields=["vendor", "prefix"]),
            models.Index(fields=["prefix"]),
            models.Index(fields=["effective_from", "effective_to"]),
        ]

    def __str__(self):
        return f"{self.vendor.code} {self.prefix} {self.rate} from {self.effective_from}"

    @property
    def is_superseded(self):
        return self.effective_to is not None and self.effective_to <= self.effective_from

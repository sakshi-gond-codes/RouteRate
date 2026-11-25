from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

increment_validator = RegexValidator(r"^\d{1,4}/\d{1,4}$", "Use the format first/next seconds, e.g. 60/60 or 1/1.")


class Vendor(models.Model):
    """A wholesale voice carrier that sends us rate decks (where we buy termination)."""

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="Short code shown in tables, e.g. KST")
    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    default_increment = models.CharField(
        max_length=10, default="60/60", validators=[increment_validator],
        help_text="Billing increment used when a deck has no increment column",
    )
    priority = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="1 = most preferred. Used as tie-breaker when two vendors have the same rate.",
    )
    is_active = models.BooleanField(default=True, help_text="Inactive vendors are ignored by LCR.")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_deck_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

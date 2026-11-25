from django.conf import settings
from django.db import models


class Country(models.Model):
    """A country (or global service) and its international dial code."""

    name = models.CharField(max_length=80, unique=True)
    iso_code = models.CharField(max_length=2)
    dial_code = models.CharField(max_length=6, unique=True, help_text="Digits only, e.g. 44 or 1876")
    region = models.CharField(max_length=40, blank=True)
    aliases = models.CharField(max_length=200, blank=True, help_text="Comma separated alternative names")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return f"{self.name} (+{self.dial_code})"

    @property
    def names(self):
        """All lower-case names used to match a vendor's destination text."""
        extra = [a.strip().lower() for a in self.aliases.split(",") if a.strip()]
        return [self.name.lower(), *extra]


class ActivityLog(models.Model):
    """Audit trail of important actions (uploads, activations, LCR runs, rate sheets, user changes)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30)
    description = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}: {self.description}"

    ICONS = {
        "login": "box-arrow-in-right", "upload": "cloud-arrow-up", "process": "gear",
        "activate": "check2-circle", "discard": "x-circle", "lcr": "diagram-3",
        "ratesheet": "file-earmark-spreadsheet", "vendor": "building", "customer": "people",
        "margin": "percent", "block": "slash-circle", "user": "person-gear",
    }

    @property
    def icon(self):
        return self.ICONS.get(self.action, "dot")

    @classmethod
    def record(cls, user, action, description):
        return cls.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            description=description[:300],
        )

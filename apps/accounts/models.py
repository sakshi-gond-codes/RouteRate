from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user with a single business role."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Rate Analyst"
        VIEWER = "viewer", "Viewer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        ordering = ["first_name", "username"]

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def can_manage_rates(self):
        """Admins and Rate Analysts can upload decks, run LCR and publish rate sheets."""
        return self.is_admin_role or self.role == self.Role.ANALYST

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p] or [self.username]
        return "".join(p[0] for p in parts[:2]).upper()

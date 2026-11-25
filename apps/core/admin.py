from django.contrib import admin

from .models import ActivityLog, Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "dial_code", "iso_code", "region")
    search_fields = ("name", "dial_code")
    list_filter = ("region",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "description")
    list_filter = ("action",)

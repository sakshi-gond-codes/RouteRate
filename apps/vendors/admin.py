from django.contrib import admin

from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "priority", "default_increment", "is_active", "last_deck_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")

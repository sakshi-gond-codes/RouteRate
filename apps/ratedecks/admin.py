from django.contrib import admin

from .models import ColumnMapping, DeckIssue, RateDeck, VendorRate


@admin.register(RateDeck)
class RateDeckAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "original_filename", "deck_type", "status", "prefix_count", "error_rows", "uploaded_at")
    list_filter = ("status", "deck_type", "vendor")


@admin.register(VendorRate)
class VendorRateAdmin(admin.ModelAdmin):
    list_display = ("vendor", "prefix", "destination", "rate", "effective_from", "effective_to", "change")
    list_filter = ("vendor",)
    search_fields = ("prefix", "destination")


admin.site.register(ColumnMapping)
admin.site.register(DeckIssue)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class RouteRateUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("RouteRate", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("RouteRate", {"fields": ("role",)}),)

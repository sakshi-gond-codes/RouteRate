from django.urls import path

from . import views

app_name = "routing"

urlpatterns = [
    path("compare/", views.compare, name="compare"),
    path("lcr/", views.lcr_list, name="lcr_list"),
    path("lcr/<int:pk>/", views.lcr_detail, name="lcr_detail"),
    path("lcr/<int:pk>/delete/", views.lcr_delete, name="lcr_delete"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_form, name="customer_create"),
    path("customers/<int:pk>/edit/", views.customer_form, name="customer_edit"),
    path("margins/", views.margin_list, name="margin_list"),
    path("margins/new/", views.margin_form, name="margin_create"),
    path("margins/<int:pk>/edit/", views.margin_form, name="margin_edit"),
    path("margins/<int:pk>/delete/", views.margin_delete, name="margin_delete"),
    path("blocked/", views.blocked_list, name="blocked_list"),
    path("blocked/new/", views.blocked_form, name="blocked_create"),
    path("blocked/<int:pk>/edit/", views.blocked_form, name="blocked_edit"),
    path("blocked/<int:pk>/delete/", views.blocked_delete, name="blocked_delete"),
    path("ratesheets/", views.ratesheet_list, name="ratesheet_list"),
    path("ratesheets/new/", views.ratesheet_create, name="ratesheet_create"),
    path("ratesheets/<int:pk>/", views.ratesheet_detail, name="ratesheet_detail"),
    path("ratesheets/<int:pk>/export/", views.ratesheet_export, name="ratesheet_export"),
]

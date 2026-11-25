from django.urls import path

from . import views

app_name = "ratedecks"

urlpatterns = [
    path("", views.history, name="history"),
    path("upload/", views.upload, name="upload"),
    path("errors/", views.error_reports, name="errors"),
    path("rates/", views.rate_browser, name="rates"),
    path("<int:pk>/", views.deck_detail, name="detail"),
    path("<int:pk>/map/", views.map_columns, name="map"),
    path("<int:pk>/activate/", views.deck_activate, name="activate"),
    path("<int:pk>/discard/", views.deck_discard, name="discard"),
    path("<int:pk>/download/", views.deck_download, name="download"),
    path("<int:pk>/export/<str:kind>/", views.deck_export, name="export"),
]

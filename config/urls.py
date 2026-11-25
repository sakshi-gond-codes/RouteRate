from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("vendors/", include("apps.vendors.urls")),
    path("decks/", include("apps.ratedecks.urls")),
    path("routing/", include("apps.routing.urls")),
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"

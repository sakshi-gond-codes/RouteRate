from django.conf import settings


def app_context(request):
    return {
        "APP_NAME": "RouteRate",
        "CURRENCY": settings.ROUTERATE["CURRENCY"],
    }

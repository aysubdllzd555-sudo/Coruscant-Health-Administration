from django.conf import settings


def app_meta(request):
    return {"APP_VERSION": settings.APP_VERSION, "GIT_SHA": settings.GIT_SHA, "SHOW_DEMO": settings.SHOW_DEMO_ACCOUNTS}

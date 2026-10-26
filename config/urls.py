from django.contrib import admin
from django.urls import include, path

from accounts.views import healthz
from clinic.views import home

admin.site.site_header = "Coruscant Health Administration"
admin.site.site_title = "CHA admin"
admin.site.index_title = "Database administration"

urlpatterns = [
    path("", home, name="home"),
    path("healthz", healthz, name="healthz"),
    path("accounts/", include("accounts.urls")),
    path("admin/", admin.site.urls),
    path("", include("clinic.urls")),
]

handler403 = "config.errors.forbidden"
handler404 = "config.errors.not_found"

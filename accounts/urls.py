from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CHALoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("pending/", views.pending, name="pending"),
    path("console/approvals/", views.approvals, name="approvals"),
    path("console/approvals/<int:pk>/", views.decide, name="decide"),
    path("console/users/", views.users, name="users"),
    path("console/monitor/", views.monitor, name="monitor"),
]

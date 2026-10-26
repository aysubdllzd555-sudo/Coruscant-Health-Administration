from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views as accounts
from clinic import views as clinic

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", accounts.health, name="health"),

    # accounts
    path("", auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", accounts.register, name="register"),
    path("pending/", accounts.pending, name="pending"),
    path("dashboard/", accounts.dashboard, name="dashboard"),
    path("administration/", accounts.admin_panel, name="admin_panel"),
    path("administration/users/<int:user_id>/", accounts.approve_user, name="approve_user"),

    # patient
    path("my-health/", clinic.patient_home, name="patient_home"),
    path("my-health/readings/", clinic.add_reading, name="add_reading"),
    path("my-health/upload/", clinic.upload_csv, name="upload_csv"),

    # doctor
    path("patients/", clinic.doctor_patients, name="doctor_patients"),
    path("patients/<int:patient_id>/", clinic.patient_detail, name="patient_detail"),
    path("patients/<int:patient_id>/report/", clinic.write_report, name="write_report"),
    path("patients/<int:patient_id>/order/", clinic.create_order, name="create_order"),
    path("patients/<int:patient_id>/documents/", clinic.upload_document, name="upload_document"),
    path("patients/<int:patient_id>/messages/", clinic.send_message, name="send_message"),

    # department
    path("orders/", clinic.department_orders, name="department_orders"),
    path("orders/<int:order_id>/start/", clinic.start_order, name="start_order"),
    path("orders/<int:order_id>/complete/", clinic.complete_order, name="complete_order"),

    # emergency services
    path("emergency/", clinic.emergency, name="emergency"),

    path("documents/<int:document_id>/", clinic.download_document, name="download_document"),
]

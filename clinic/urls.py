from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    # patient
    path("me/", views.my_dashboard, name="my_dashboard"),
    path("me/readings/upload/", views.upload_readings, name="upload_readings"),
    path("me/readings/new/", views.add_reading, name="add_reading"),
    path("me/devices/", views.my_devices, name="my_devices"),
    path("me/devices/<int:pk>/revoke/", views.revoke_device, name="revoke_device"),
    path("me/reports/", views.my_reports, name="my_reports"),
    path("me/documents/", views.my_documents, name="my_documents"),
    path("me/messages/", views.messages_view, name="my_messages"),
    # doctor
    path("worklist/", views.worklist, name="worklist"),
    path("patients/<str:mrn>/", views.patient_chart, name="patient_chart"),
    path("patients/<str:mrn>/reports/", views.write_report, name="write_report"),
    path("patients/<str:mrn>/orders/", views.place_order, name="place_order"),
    path("patients/<str:mrn>/assign/", views.assign_doctor, name="assign_doctor"),
    path("patients/<str:mrn>/documents/", views.upload_document, name="upload_document"),
    path("patients/<str:mrn>/messages/", views.messages_view, name="patient_messages"),
    path("patients/<str:mrn>/ed/", views.ed_update, name="ed_update"),
    path("orders/<int:pk>/cancel/", views.cancel_order, name="cancel_order"),
    # department
    path("department/", views.department_queue, name="department_queue"),
    path("orders/<int:pk>/advance/", views.advance_order, name="advance_order"),
    path("orders/<int:pk>/result/", views.result_order, name="result_order"),
    # emergency
    path("ed/", views.ed_board, name="ed_board"),
    path("ed/intake/", views.ed_intake, name="ed_intake"),
    # documents
    path("documents/<uuid:uid>/", views.download_document, name="download_document"),
    # API
    path("api/v1/readings", views.api_readings, name="api_readings"),
    path("api/v1/patients/<str:mrn>/readings", views.api_patient_readings, name="api_patient_readings"),
]

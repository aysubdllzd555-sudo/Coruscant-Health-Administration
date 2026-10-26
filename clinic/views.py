import csv
import io

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from . import encryption
from .forms import CsvUploadForm, DocumentForm, EmergencyForm, MessageForm, OrderForm, ReadingForm, ReportForm, ResultForm
from .models import Document, Message, Order, Patient, Reading


def can_see_patient(user, patient):
    if user.role in (User.ADMIN, User.DOCTOR, User.EMERGENCY):
        return True
    if user.role == User.PATIENT:
        return patient.user_id == user.id
    return False


def back_to_patient(request, patient):
    if request.user.role == User.PATIENT:
        return redirect("patient_home")
    return redirect("patient_detail", patient_id=patient.id)


def save_document(file, patient, user, title, order=None):
    nonce, data = encryption.encrypt(file.read())
    return Document.objects.create(
        patient=patient, uploaded_by=user, order=order, title=title, filename=file.name,
        content_type=file.content_type or "application/octet-stream", nonce=nonce, encrypted_data=data,
    )


# ---------------- Patient ----------------

@role_required(User.PATIENT)
def patient_home(request):
    patient = get_object_or_404(Patient, user=request.user)
    context = {
        "patient": patient,
        "readings": patient.readings.all()[:20],
        "reports": patient.reports.all(),
        "orders": patient.orders.all(),
        "documents": patient.documents.all(),
        "chat": patient.messages.all(),
        "reading_form": ReadingForm(initial={"recorded_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M")}),
        "csv_form": CsvUploadForm(),
        "document_form": DocumentForm(),
        "message_form": MessageForm(),
    }
    return render(request, "clinic/patient_home.html", context)


@require_POST
@role_required(User.PATIENT)
def add_reading(request):
    patient = get_object_or_404(Patient, user=request.user)
    form = ReadingForm(request.POST)
    if form.is_valid():
        reading = form.save(commit=False)
        reading.patient = patient
        reading.save()
        messages.success(request, "Reading saved.")
    else:
        messages.error(request, "Please fill in all values.")
    return redirect("patient_home")


@require_POST
@role_required(User.PATIENT)
def upload_csv(request):
    """Imports a CSV file exported from the wearable device."""
    patient = get_object_or_404(Patient, user=request.user)
    form = CsvUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a CSV file.")
        return redirect("patient_home")
    try:
        text = form.cleaned_data["file"].read().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        readings = []
        for row in rows:
            recorded_at = parse_datetime(row["recorded_at"]) or timezone.now()
            if timezone.is_naive(recorded_at):
                recorded_at = timezone.make_aware(recorded_at)
            readings.append(Reading(
                patient=patient,
                recorded_at=recorded_at,
                heart_rate=int(row["heart_rate"]),
                systolic=int(row["systolic"]),
                diastolic=int(row["diastolic"]),
                temperature=row["temperature"],
                oxygen=int(row["oxygen"]),
            ))
        Reading.objects.bulk_create(readings)
        messages.success(request, f"{len(readings)} readings imported from the device.")
    except (KeyError, ValueError, UnicodeDecodeError):
        messages.error(request, "The file format is wrong. Check the column names.")
    return redirect("patient_home")


# ---------------- Doctor ----------------

@role_required(User.DOCTOR, User.EMERGENCY)
def doctor_patients(request):
    search = request.GET.get("q", "")
    patients = Patient.objects.all()
    if search:
        patients = patients.filter(full_name__icontains=search)
    return render(request, "clinic/doctor_patients.html", {"patients": patients, "search": search})


@role_required(User.DOCTOR, User.EMERGENCY, User.PATIENT)
def patient_detail(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    if not can_see_patient(request.user, patient):
        raise PermissionDenied
    if request.user.role == User.PATIENT:
        return redirect("patient_home")
    context = {
        "patient": patient,
        "readings": patient.readings.all()[:30],
        "reports": patient.reports.all(),
        "orders": patient.orders.all(),
        "documents": patient.documents.all(),
        "chat": patient.messages.all(),
        "report_form": ReportForm(),
        "order_form": OrderForm(),
        "document_form": DocumentForm(),
        "message_form": MessageForm(),
    }
    return render(request, "clinic/patient_detail.html", context)


@require_POST
@role_required(User.DOCTOR)
def write_report(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    form = ReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.patient = patient
        report.doctor = request.user
        report.save()
        if patient.doctor is None:
            patient.doctor = request.user
            patient.save()
        messages.success(request, "Report sent to the patient.")
    return redirect("patient_detail", patient_id=patient.id)


@require_POST
@role_required(User.DOCTOR)
def create_order(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    form = OrderForm(request.POST)
    if form.is_valid():
        order = form.save(commit=False)
        order.patient = patient
        order.doctor = request.user
        order.save()
        messages.success(request, f"{order.get_service_display()} ordered from {order.get_department_display()}.")
    return redirect("patient_detail", patient_id=patient.id)


# ---------------- Department ----------------

@role_required(User.DEPARTMENT)
def department_orders(request):
    department = request.user.department or request.GET.get("department", "radiology")
    orders = Order.objects.filter(department=department)
    context = {
        "department": dict(User.DEPARTMENT_CHOICES).get(department, department),
        "open_orders": orders.exclude(status="completed"),
        "done_orders": orders.filter(status="completed")[:20],
        "result_form": ResultForm(auto_id=False),
    }
    return render(request, "clinic/department_orders.html", context)


def get_department_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.user.role != User.ADMIN and order.department != request.user.department:
        raise PermissionDenied
    return order


@require_POST
@role_required(User.DEPARTMENT)
def start_order(request, order_id):
    order = get_department_order(request, order_id)
    order.status = "in_progress"
    order.save()
    return redirect("department_orders")


@require_POST
@role_required(User.DEPARTMENT)
def complete_order(request, order_id):
    order = get_department_order(request, order_id)
    form = ResultForm(request.POST, request.FILES)
    if form.is_valid():
        order.result = form.cleaned_data["result"]
        order.status = "completed"
        order.completed_at = timezone.now()
        order.save()
        if form.cleaned_data["file"]:
            save_document(form.cleaned_data["file"], order.patient, request.user, f"{order.get_service_display()} result", order)
        messages.success(request, "Result uploaded.")
    else:
        messages.error(request, "Write the result (allowed files: pdf, png, jpg, txt, csv, dcm).")
    return redirect("department_orders")


# ---------------- Emergency services ----------------

@role_required(User.EMERGENCY, User.DOCTOR)
def emergency(request):
    form = EmergencyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        patient = form.save(commit=False)
        patient.is_emergency = True
        patient.save()
        messages.success(request, f"{patient.full_name} added.")
        return redirect("emergency")
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    patients = sorted(Patient.objects.filter(is_emergency=True), key=lambda p: order.get(p.priority, 4))
    return render(request, "clinic/emergency.html", {"form": form, "patients": patients})


# ---------------- Documents & messages (shared) ----------------

@require_POST
@role_required(User.PATIENT, User.DOCTOR, User.EMERGENCY)
def upload_document(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    if not can_see_patient(request.user, patient):
        raise PermissionDenied
    form = DocumentForm(request.POST, request.FILES)
    if form.is_valid():
        save_document(form.cleaned_data["file"], patient, request.user, form.cleaned_data["title"])
        messages.success(request, "Document encrypted and saved.")
    else:
        messages.error(request, " ".join(form.errors.get("file", ["Check the form."])))
    return back_to_patient(request, patient)


@role_required(User.PATIENT, User.DOCTOR, User.EMERGENCY, User.DEPARTMENT)
def download_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    allowed = can_see_patient(request.user, document.patient) or (
        request.user.role == User.DEPARTMENT and document.order and document.order.department == request.user.department)
    if not allowed:
        raise PermissionDenied
    data = encryption.decrypt(document.nonce, document.encrypted_data)
    response = HttpResponse(data, content_type=document.content_type)
    response["Content-Disposition"] = f'attachment; filename="{document.filename}"'
    return response


@require_POST
@role_required(User.PATIENT, User.DOCTOR, User.EMERGENCY)
def send_message(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    if not can_see_patient(request.user, patient):
        raise PermissionDenied
    form = MessageForm(request.POST)
    if form.is_valid():
        Message.objects.create(patient=patient, sender=request.user, text=form.cleaned_data["text"])
    return back_to_patient(request, patient)

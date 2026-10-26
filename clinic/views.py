import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import User
from accounts.permissions import approved_required, role_required

from . import ingest, scoring
from .forms import (
    BedUpdateForm,
    DeviceForm,
    DocumentForm,
    EmergencyIntakeForm,
    ManualReadingForm,
    MessageForm,
    OrderForm,
    ReadingUploadForm,
    ReportForm,
    ResultForm,
)
from .models import AuditEvent, Department, Device, Document, Order, Patient, Reading

R = User.Role

ED_ZONES = [
    ("acute", "Acute", [f"A{i}" for i in range(1, 11)]),
    ("minor", "Minor care", [f"MC{i}" for i in range(1, 5)]),
    ("obs", "Observation", [f"O{i}" for i in range(1, 4)]),
]
ALL_BAYS = [b for _, _, bays in ED_ZONES for b in bays]


def home(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("accounts:login")
    if not (user.is_approved or user.is_superuser):
        return redirect("accounts:pending")
    target = {
        R.PATIENT: "clinic:my_dashboard",
        R.DOCTOR: "clinic:worklist",
        R.DEPARTMENT: "clinic:department_queue",
        R.EMERGENCY: "clinic:ed_board",
    }.get(user.role, "accounts:monitor")
    return redirect(target)


def _patient_for(request, mrn):
    patient = get_object_or_404(Patient.objects.select_related("user", "primary_doctor"), mrn=mrn)
    if not patient.can_be_viewed_by(request.user):
        raise PermissionDenied
    return patient


def _own_patient(request):
    patient = getattr(request.user, "patient", None)
    if patient is None:
        raise Http404("No patient record is linked to this account")
    return patient


def _chart_series(readings):
    readings = list(reversed(readings))
    return [
        {
            "t": r.recorded_at.isoformat(),
            "hr": r.heart_rate,
            "spo2": r.spo2,
            "temp": float(r.temperature_c) if r.temperature_c is not None else None,
            "sys": r.systolic,
            "dia": r.diastolic,
            "rr": r.resp_rate,
            "glu": float(r.glucose) if r.glucose is not None else None,
            "news2": r.news2,
        }
        for r in readings
    ]


# ------------------------------------------------------------------ Patient


@role_required(R.PATIENT)
def my_dashboard(request):
    patient = _own_patient(request)
    readings = patient.recent_readings(60)
    latest = readings[0] if readings else None
    reports = patient.reports.select_related("doctor")[:3]
    unread = patient.reports.filter(read_by_patient_at__isnull=True).count()
    ctx = {
        "patient": patient,
        "latest": latest,
        "readings": readings[:8],
        "series": _chart_series(readings),
        "trend": scoring.trend(readings[:10]),
        "reports": reports,
        "unread_reports": unread,
        "orders": patient.orders.select_related("service__department")[:5],
        "devices": patient.devices.all(),
        "upload_form": ReadingUploadForm(),
        "manual_form": ManualReadingForm(initial={"recorded_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M")}),
    }
    return render(request, "clinic/patient/dashboard.html", ctx)


@require_POST
@role_required(R.PATIENT)
def upload_readings(request):
    patient = _own_patient(request)
    form = ReadingUploadForm(request.POST, request.FILES)
    if form.is_valid():
        f = form.cleaned_data["file"]
        try:
            rows = ingest.parse_file(f.name, f.read())
        except (ingest.IngestError, ValueError) as exc:
            messages.error(request, f"Upload rejected: {exc}")
        else:
            ingest.store(patient, rows, source=Reading.Source.UPLOAD)
            AuditEvent.log(request, "upload_readings", f"{len(rows)} rows", patient)
            messages.success(request, f"{len(rows)} readings uploaded from {f.name}.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("clinic:my_dashboard")


@require_POST
@role_required(R.PATIENT)
def add_reading(request):
    patient = _own_patient(request)
    form = ManualReadingForm(request.POST)
    if form.is_valid():
        r = form.save(commit=False)
        r.patient, r.source = patient, Reading.Source.MANUAL
        r.save()
        messages.success(request, "Reading saved.")
    else:
        messages.error(request, "Please check the reading values.")
    return redirect("clinic:my_dashboard")


@role_required(R.PATIENT)
def my_devices(request):
    patient = _own_patient(request)
    form = DeviceForm(request.POST or None)
    new_token = None
    if request.method == "POST" and form.is_valid():
        device = form.save(commit=False)
        device.patient = patient
        new_token = device.issue_token()
        device.save()
        AuditEvent.log(request, "pair_device", device.label, patient)
    return render(request, "clinic/patient/devices.html", {
        "patient": patient, "devices": patient.devices.annotate(n=Count("readings")),
        "form": DeviceForm() if new_token else form, "new_token": new_token,
        "api_url": request.build_absolute_uri(reverse("clinic:api_readings")),
    })


@require_POST
@role_required(R.PATIENT)
def revoke_device(request, pk):
    device = get_object_or_404(Device, pk=pk, patient=_own_patient(request))
    device.active = False
    device.save(update_fields=["active"])
    messages.info(request, f"{device.label} was disconnected; its token no longer works.")
    return redirect("clinic:my_devices")


@role_required(R.PATIENT)
def my_reports(request):
    patient = _own_patient(request)
    reports = list(patient.reports.select_related("doctor"))
    patient.reports.filter(read_by_patient_at__isnull=True).update(read_by_patient_at=timezone.now())
    return render(request, "clinic/patient/reports.html", {"patient": patient, "reports": reports})


# ------------------------------------------------------------------ Doctor


@role_required(R.DOCTOR, R.EMERGENCY)
def worklist(request):
    q = request.GET.get("q", "").strip()
    scope = request.GET.get("scope", "mine" if request.user.is_doctor else "all")
    patients = Patient.objects.select_related("primary_doctor").annotate(
        last_reading=Max("readings__recorded_at"),
        open_orders=Count("orders", filter=Q(orders__status__in=["ordered", "accepted", "in_progress"]), distinct=True),
    ).prefetch_related(Prefetch("readings", queryset=Reading.objects.order_by("-recorded_at"), to_attr="_rs"))
    if scope == "mine":
        patients = patients.filter(primary_doctor=request.user)
    if q:
        patients = patients.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(mrn__icontains=q) | Q(chief_complaint__icontains=q))
    rows = []
    for p in patients[:200]:
        rs = p._rs[:10]
        latest = rs[0] if rs else None
        rows.append({"p": p, "latest": latest, "news2": latest.news2 if latest else None,
                     "risk": latest.risk if latest else "unknown", "trend": scoring.trend(rs)})
    order = {"high": 0, "medium": 1, "low": 2, "none": 3, "unknown": 4}
    rows.sort(key=lambda r: (order[r["risk"]], -(r["news2"] or 0)))
    summary = {
        "high": sum(r["risk"] == "high" for r in rows),
        "worsening": sum(r["trend"] == "worsening" for r in rows),
        "results": Order.objects.filter(ordered_by=request.user, status="resulted", resulted_at__gte=timezone.now() - timezone.timedelta(days=2)).count(),
        "total": len(rows),
    }
    return render(request, "clinic/doctor/worklist.html", {"rows": rows, "q": q, "scope": scope, "summary": summary})


@approved_required
def patient_chart(request, mrn):
    patient = _patient_for(request, mrn)
    if request.user.is_patient:
        return redirect("clinic:my_dashboard")
    readings = patient.recent_readings(100)
    AuditEvent.log(request, "view_chart", patient.mrn, patient)
    ctx = {
        "patient": patient,
        "latest": readings[0] if readings else None,
        "readings": readings[:25],
        "series": _chart_series(readings),
        "trend": scoring.trend(readings[:10]),
        "reports": patient.reports.select_related("doctor"),
        "orders": patient.orders.select_related("service__department", "ordered_by"),
        "documents": patient.documents.select_related("uploaded_by"),
        "thread": patient.messages.select_related("sender"),
        "report_form": ReportForm(initial={"condition": scoring.trend(readings[:10]) if scoring.trend(readings[:10]) in ("improving", "stable", "worsening") else "stable"}),
        "order_form": OrderForm(auto_id="ord_%s"),
        "doc_form": DocumentForm(auto_id="doc_%s"),
        "msg_form": MessageForm(),
        "bed_form": BedUpdateForm(initial={"ed_status": patient.ed_status if patient.ed_status != "none" else "waiting", "bay": patient.bay, "acuity": patient.acuity or 3}),
        "bays": ALL_BAYS,
        "doctors": User.objects.filter(role=R.DOCTOR, is_approved=True),
    }
    return render(request, "clinic/doctor/chart.html", ctx)


@require_POST
@role_required(R.DOCTOR)
def write_report(request, mrn):
    patient = _patient_for(request, mrn)
    form = ReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.patient, report.doctor = patient, request.user
        report.save()
        if patient.primary_doctor_id is None:
            patient.primary_doctor = request.user
            patient.save(update_fields=["primary_doctor"])
        AuditEvent.log(request, "write_report", report.title, patient)
        messages.success(request, "Report signed and shared with the patient.")
    else:
        messages.error(request, "The report is incomplete — title, assessment and suggestions are required.")
    return redirect(reverse("clinic:patient_chart", args=[mrn]) + "#reports")


@require_POST
@role_required(R.DOCTOR, R.EMERGENCY)
def place_order(request, mrn):
    patient = _patient_for(request, mrn)
    form = OrderForm(request.POST)
    if form.is_valid():
        order = form.save(commit=False)
        order.patient, order.ordered_by = patient, request.user
        order.save()
        AuditEvent.log(request, "place_order", f"{order.service} ({order.priority})", patient)
        messages.success(request, f"{order.service} sent to {order.service.department}.")
    else:
        messages.error(request, "Choose a service and give a clinical indication.")
    return redirect(reverse("clinic:patient_chart", args=[mrn]) + "#orders")


@require_POST
@role_required(R.DOCTOR, R.EMERGENCY)
def assign_doctor(request, mrn):
    patient = _patient_for(request, mrn)
    doctor = get_object_or_404(User, pk=request.POST.get("doctor"), role=R.DOCTOR)
    patient.primary_doctor = doctor
    patient.save(update_fields=["primary_doctor"])
    messages.success(request, f"Dr. {doctor.display_name} is now the attending physician.")
    return redirect("clinic:patient_chart", mrn=mrn)


@require_POST
@role_required(R.DOCTOR, R.EMERGENCY)
def cancel_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.is_open:
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        AuditEvent.log(request, "cancel_order", str(order), order.patient)
    return redirect(reverse("clinic:patient_chart", args=[order.patient.mrn]) + "#orders")


# ------------------------------------------------------------------ Department


@role_required(R.DEPARTMENT)
def department_queue(request):
    user = request.user
    departments = Department.objects.annotate(open=Count("services__orders", filter=Q(services__orders__status__in=["ordered", "accepted", "in_progress"])))
    code = request.GET.get("dept") or (user.department.code if user.department else None)
    if not user.is_admin_role:
        code = user.department.code if user.department else None
    dept = Department.objects.filter(code=code).first() if code else departments.first()
    status = request.GET.get("status", "open")
    orders = Order.objects.select_related("patient", "service", "ordered_by", "assigned_to").filter(service__department=dept)
    if status == "open":
        orders = orders.filter(status__in=["ordered", "accepted", "in_progress"])
    elif status == "done":
        orders = orders.filter(status="resulted")[:50]
    prio = {"stat": 0, "urgent": 1, "routine": 2}
    orders = sorted(orders, key=lambda o: (prio[o.priority], o.created_at)) if status == "open" else orders
    columns = {s: [o for o in orders if o.status == s] for s in ("ordered", "accepted", "in_progress")} if status == "open" else None
    return render(request, "clinic/department/queue.html", {
        "dept": dept, "departments": departments, "orders": orders, "columns": columns,
        "status": status, "result_form": ResultForm(),
    })


def _dept_order(request, pk):
    order = get_object_or_404(Order.objects.select_related("service__department", "patient"), pk=pk)
    if not request.user.is_admin_role and order.service.department_id != request.user.department_id:
        raise PermissionDenied
    return order


@require_POST
@role_required(R.DEPARTMENT)
def advance_order(request, pk):
    order = _dept_order(request, pk)
    if order.advance(request.user):
        AuditEvent.log(request, f"order_{order.status}", str(order), order.patient)
    return redirect(f"{reverse('clinic:department_queue')}?dept={order.department.code}")


@role_required(R.DEPARTMENT)
def result_order(request, pk):
    order = _dept_order(request, pk)
    form = ResultForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            order.record_result(request.user, form.cleaned_data["result_summary"], form.cleaned_data["result_flag"])
            f = form.cleaned_data.get("file")
            if f:
                Document.seal(
                    data=f.read(), patient=order.patient, uploaded_by=request.user, order=order,
                    category=Document.Category.IMAGING if order.department.kind == "imaging" else Document.Category.LAB,
                    title=f"{order.service.name} result", original_name=f.name[:200],
                    content_type=f.content_type or "application/octet-stream",
                )
            AuditEvent.log(request, "order_resulted", str(order), order.patient)
        messages.success(request, f"Result for {order.patient.display_name} uploaded and sent to the ordering clinician.")
        return redirect(f"{reverse('clinic:department_queue')}?dept={order.department.code}")
    return render(request, "clinic/department/result.html", {"order": order, "form": form})


# ------------------------------------------------------------------ Emergency


@role_required(R.EMERGENCY, R.DOCTOR)
def ed_board(request):
    active = Patient.objects.filter(ed_status__in=["inbound", "waiting", "in_bay"]).select_related("primary_doctor").annotate(
        open_orders=Count("orders", filter=Q(orders__status__in=["ordered", "accepted", "in_progress"]))
    )
    by_bay = {p.bay: p for p in active if p.ed_status == "in_bay" and p.bay}
    zone = request.GET.get("zone", "all")
    zones = [(code, label, [(b, by_bay.get(b)) for b in bays]) for code, label, bays in ED_ZONES if zone in ("all", code)]
    waiting = sorted([p for p in active if p.ed_status == "waiting"], key=lambda p: (p.acuity or 9, p.arrived_at))
    inbound = [p for p in active if p.ed_status == "inbound"]
    in_bay = [p for p in active if p.ed_status == "in_bay"]
    occupied = len(by_bay)
    open_orders = Order.objects.filter(patient__in=active, status__in=["ordered", "accepted", "in_progress"]).values("service__department__name").annotate(n=Count("id"))
    ctx = {
        "zones": zones, "zone": zone, "waiting": waiting, "inbound": inbound,
        "occupied": occupied, "capacity": len(ALL_BAYS),
        "max_wait": max((p.minutes_in_ed or 0 for p in waiting), default=0),
        "dept_load": {d["service__department__name"]: d["n"] for d in open_orders},
        "departments": Department.objects.all(),
        "form": EmergencyIntakeForm(), "free_bays": [b for b in ALL_BAYS if b not in by_bay],
        "census": len(in_bay) + len(waiting),
    }
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"waiting": len(waiting), "occupied": occupied, "inbound": len(inbound)})
    return render(request, "clinic/emergency/board.html", ctx)


@role_required(R.EMERGENCY, R.DOCTOR)
def ed_intake(request):
    form = EmergencyIntakeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        bay = d["bay"].strip().upper()
        if bay and Patient.objects.filter(bay=bay, ed_status="in_bay").exists():
            form.add_error("bay", f"{bay} is occupied.")
        else:
            with transaction.atomic():
                p = Patient.objects.create(
                    first_name=d["first_name"], last_name=d["last_name"], approx_age=d["approx_age"],
                    sex=d["sex"], species=d["species"] or "Human", allergies=d["allergies"],
                    chief_complaint=d["chief_complaint"], acuity=d["acuity"], arrival_mode=d["arrival_mode"],
                    bay=bay, ed_status="in_bay" if bay else "waiting", arrived_at=timezone.now(),
                    is_unidentified=not (d["first_name"] or d["last_name"]),
                    brainworm_screened=d["brainworm_screened"],
                    source=Patient.Source.EMERGENCY, created_by=request.user,
                    primary_doctor=request.user if request.user.is_doctor else None,
                )
                vitals = {k: d[k] for k in ("heart_rate", "spo2", "systolic", "resp_rate", "temperature_c") if d.get(k) is not None}
                if vitals:
                    Reading.objects.create(patient=p, source=Reading.Source.MANUAL, **vitals)
                AuditEvent.log(request, "ed_intake", f"ESI {p.acuity} · {p.chief_complaint}", p)
            messages.success(request, f"{p.display_name} registered · {p.mrn} · {'bay ' + bay if bay else 'waiting room'}.")
            if request.POST.get("then") == "chart":
                return redirect("clinic:patient_chart", mrn=p.mrn)
            return redirect("clinic:ed_board")
    if request.method == "POST":
        messages.error(request, "Chief complaint and acuity are required.")
    bay_value = (form.data.get("bay") if form.is_bound else request.GET.get("bay", "")) or ""
    return render(request, "clinic/emergency/intake.html", {"form": form, "bay_value": bay_value.upper()[:8], "free_bays": [b for b in ALL_BAYS if not Patient.objects.filter(bay=b, ed_status="in_bay").exists()]})


@require_POST
@role_required(R.EMERGENCY, R.DOCTOR)
def ed_update(request, mrn):
    patient = _patient_for(request, mrn)
    form = BedUpdateForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        bay = d["bay"].strip().upper() if d["ed_status"] == "in_bay" else ""
        if d["ed_status"] == "in_bay" and not bay:
            messages.error(request, "Choose a bay.")
        elif bay and Patient.objects.filter(bay=bay, ed_status="in_bay").exclude(pk=patient.pk).exists():
            messages.error(request, f"{bay} is already occupied.")
        else:
            patient.ed_status, patient.bay, patient.acuity = d["ed_status"], bay, d["acuity"]
            patient.arrived_at = patient.arrived_at or timezone.now()
            patient.save(update_fields=["ed_status", "bay", "acuity", "arrived_at"])
            AuditEvent.log(request, "ed_move", f"{patient.get_ed_status_display()} {bay}", patient)
            messages.success(request, f"{patient.display_name}: {patient.get_ed_status_display()}{' · ' + bay if bay else ''}.")
    return redirect(request.POST.get("next") or reverse("clinic:ed_board"))


# ------------------------------------------------------------------ Documents & messages


@require_POST
@approved_required
def upload_document(request, mrn):
    patient = _patient_for(request, mrn)
    if request.user.is_department:
        raise PermissionDenied
    form = DocumentForm(request.POST, request.FILES)
    if form.is_valid():
        f = form.cleaned_data["file"]
        doc = Document.seal(
            data=f.read(), patient=patient, uploaded_by=request.user,
            category=form.cleaned_data["category"], title=form.cleaned_data["title"],
            original_name=f.name[:200], content_type=f.content_type or "application/octet-stream",
        )
        AuditEvent.log(request, "upload_document", doc.title, patient)
        messages.success(request, f"“{doc.title}” encrypted with AES-256-GCM and stored.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    if request.user.is_patient:
        return redirect("clinic:my_documents")
    return redirect(reverse("clinic:patient_chart", args=[mrn]) + "#documents")


@role_required(R.PATIENT)
def my_documents(request):
    patient = _own_patient(request)
    return render(request, "clinic/patient/documents.html", {
        "patient": patient, "documents": patient.documents.select_related("uploaded_by", "order__service"), "form": DocumentForm(),
    })


@approved_required
def download_document(request, uid):
    doc = get_object_or_404(Document.objects.select_related("patient", "order__service"), uid=uid)
    if not doc.can_be_viewed_by(request.user):
        raise PermissionDenied
    data = doc.decrypt()
    AuditEvent.log(request, "download_document", doc.title, doc.patient)
    inline = request.GET.get("inline") == "1" and doc.content_type in {"application/pdf", "image/png", "image/jpeg", "text/plain"}
    resp = HttpResponse(data, content_type=doc.content_type if inline else "application/octet-stream")
    disposition = "inline" if inline else "attachment"
    safe_name = doc.original_name.replace('"', "")
    resp["Content-Disposition"] = f'{disposition}; filename="{safe_name}"'
    resp["Cache-Control"] = "no-store, private"
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
    return resp


@approved_required
def messages_view(request, mrn=None):
    if request.user.is_patient:
        patient = _own_patient(request)
    else:
        patient = _patient_for(request, mrn)
    if request.user.is_department:
        raise PermissionDenied
    form = MessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        patient.messages.create(sender=request.user, body=form.cleaned_data["body"])
        if request.user.is_patient:
            return redirect("clinic:my_messages")
        return redirect(reverse("clinic:patient_chart", args=[patient.mrn]) + "#messages")
    if not request.user.is_patient:
        return redirect(reverse("clinic:patient_chart", args=[patient.mrn]) + "#messages")
    return render(request, "clinic/patient/messages.html", {"patient": patient, "thread": patient.messages.select_related("sender"), "form": MessageForm()})


# ------------------------------------------------------------------ Device API


@csrf_exempt
@require_http_methods(["POST"])
def api_readings(request):
    """POST /api/v1/readings  —  Authorization: Bearer <device token>
    Body: {"readings": [{"recorded_at": "...", "heart_rate": 72, ...}]} or a single object."""
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    device = Device.authenticate(token)
    if device is None:
        return JsonResponse({"error": "invalid or revoked device token"}, status=401)
    try:
        payload = json.loads(request.body or b"{}")
        items = payload.get("readings", [payload]) if isinstance(payload, dict) else payload
        rows = ingest.parse_rows(items)
    except (ValueError, ingest.IngestError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    objs = ingest.store(device.patient, rows, device=device)
    latest = max(objs, key=lambda r: r.recorded_at)
    return JsonResponse({"accepted": len(objs), "patient": device.patient.mrn, "latest_news2": latest.news2}, status=201)


@approved_required
def api_patient_readings(request, mrn):
    patient = _patient_for(request, mrn)
    return JsonResponse({"mrn": patient.mrn, "series": _chart_series(patient.recent_readings(200))})

import platform
import time

import django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from clinic.models import AuditEvent, Device, DoctorProfile, Document, Order, Patient, Reading, Report

from .forms import LoginForm, RegistrationForm
from .models import User
from .permissions import role_required

STARTED_AT = time.time()


class CHALoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.role = form.cleaned_data["role"]
            user.is_approved = False
            if user.role == User.Role.DEPARTMENT:
                user.department = form.cleaned_data["department"]
            user.save()
            if user.role == User.Role.PATIENT:
                Patient.objects.create(
                    user=user,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    date_of_birth=form.cleaned_data["date_of_birth"],
                    sex=form.cleaned_data.get("sex") or Patient.Sex.OTHER,
                    district=form.cleaned_data.get("district", ""),
                    allergies=form.cleaned_data.get("allergies", ""),
                    phone=user.phone,
                    source=Patient.Source.REGISTRATION,
                )
            elif user.role == User.Role.DOCTOR:
                DoctorProfile.objects.create(
                    user=user,
                    specialty=form.cleaned_data.get("specialty", ""),
                    license_number=form.cleaned_data["license_number"],
                )
            AuditEvent.log(request, "register", f"{user.username} as {user.role}")
        login(request, user)
        return redirect("accounts:pending")
    return render(request, "accounts/register.html", {"form": form})


def pending(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_approved:
        return redirect("home")
    return render(request, "accounts/pending.html")


# ---------------- Administrator console ----------------


@role_required(User.Role.ADMIN)
def approvals(request):
    queue = User.objects.filter(is_approved=False, rejected=False).select_related(
        "doctor_profile", "patient", "department"
    ).order_by("date_joined")
    return render(request, "accounts/approvals.html", {"queue": queue})


@require_POST
@role_required(User.Role.ADMIN)
def decide(request, pk):
    target = get_object_or_404(User, pk=pk)
    decision = request.POST.get("decision")
    if decision == "approve":
        target.approve(request.user)
        AuditEvent.log(request, "approve_user", target.username)
        messages.success(request, f"{target.display_name} approved as {target.get_role_display().lower()}.")
    elif decision == "reject":
        target.reject(request.user)
        AuditEvent.log(request, "reject_user", target.username)
        messages.info(request, f"{target.display_name} was rejected.")
    return redirect(request.POST.get("next") or "accounts:approvals")


@role_required(User.Role.ADMIN)
def users(request):
    role = request.GET.get("role", "")
    qs = User.objects.select_related("department").order_by("role", "last_name")
    if role:
        qs = qs.filter(role=role)
    counts = dict(User.objects.values_list("role").annotate(n=Count("id")))
    return render(request, "accounts/users.html", {"users": qs, "role": role, "roles": User.Role.choices, "counts": counts})


def _pending_migrations():
    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


@role_required(User.Role.ADMIN)
def monitor(request):
    since = timezone.now() - timezone.timedelta(hours=24)
    t0 = time.perf_counter()
    with connection.cursor() as c:
        c.execute("SELECT 1")
    db_ms = (time.perf_counter() - t0) * 1000
    pending_migrations = _pending_migrations()
    from django.db.migrations.recorder import MigrationRecorder

    applied = MigrationRecorder(connection).applied_migrations()
    ctx = {
        "stats": [
            ("Patients", Patient.objects.count()),
            ("Doctors", User.objects.filter(role=User.Role.DOCTOR, is_approved=True).count()),
            ("Readings (24h)", Reading.objects.filter(created_at__gte=since).count()),
            ("Reports", Report.objects.count()),
            ("Open orders", Order.objects.filter(status__in=["ordered", "accepted", "in_progress"]).count()),
            ("Encrypted documents", Document.objects.count()),
            ("Active devices", Device.objects.filter(active=True).count()),
            ("Pending approvals", User.objects.filter(is_approved=False, rejected=False).count()),
        ],
        "db_vendor": connection.vendor,
        "db_ms": db_ms,
        "pending_migrations": pending_migrations,
        "applied_count": len(applied),
        "uptime_min": int((time.time() - STARTED_AT) // 60),
        "python": platform.python_version(),
        "django": django.get_version(),
        "events": AuditEvent.objects.select_related("actor", "patient")[:40],
        "debug": settings.DEBUG,
    }
    return render(request, "accounts/monitor.html", ctx)


def healthz(request):
    """Liveness/readiness probe for the load balancer and CI smoke test."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        db = "ok"
    except Exception:  # pragma: no cover - only on outage
        db = "down"
    status = 200 if db == "ok" else 503
    return JsonResponse({"status": "ok" if status == 200 else "degraded", "db": db,
                         "version": settings.APP_VERSION, "commit": settings.GIT_SHA}, status=status)

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clinic.models import Document, Order, Patient, Reading, Report

from .decorators import role_required
from .forms import RegisterForm
from .models import User


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if user.role == User.PATIENT:
            Patient.objects.create(
                user=user,
                full_name=user.get_full_name() or user.username,
                date_of_birth=form.cleaned_data["date_of_birth"],
                phone=user.phone,
            )
        login(request, user)
        return redirect("pending")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def pending(request):
    if request.user.is_approved:
        return redirect("dashboard")
    return render(request, "accounts/pending.html")


@login_required
def dashboard(request):
    """Sends every user to the main page of their role."""
    if not request.user.is_approved:
        return redirect("pending")
    pages = {
        User.PATIENT: "patient_home",
        User.DOCTOR: "doctor_patients",
        User.DEPARTMENT: "department_orders",
        User.EMERGENCY: "emergency",
        User.ADMIN: "admin_panel",
    }
    return redirect(pages[request.user.role])


@role_required(User.ADMIN)
def admin_panel(request):
    context = {
        "waiting": User.objects.filter(is_approved=False).order_by("date_joined"),
        "stats": {
            "Patients": Patient.objects.count(),
            "Doctors": User.objects.filter(role=User.DOCTOR, is_approved=True).count(),
            "Readings": Reading.objects.count(),
            "Reports": Report.objects.count(),
            "Open orders": Order.objects.exclude(status="completed").count(),
            "Documents": Document.objects.count(),
        },
        "users": User.objects.filter(is_approved=True).order_by("role", "username"),
        "database": connection.vendor,
    }
    return render(request, "accounts/admin_panel.html", context)


@require_POST
@role_required(User.ADMIN)
def approve_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.POST.get("action") == "approve":
        user.is_approved = True
        user.save()
        messages.success(request, f"{user} was approved.")
    else:
        user.delete()
        messages.info(request, "Registration rejected and removed.")
    return redirect("admin_panel")


def health(request):
    """Used by Render and the CI/CD pipeline to check that the app is running."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})

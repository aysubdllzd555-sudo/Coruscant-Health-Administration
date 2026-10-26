from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """One account model for every stakeholder; access is governed by `role` + `is_approved`."""

    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"
        DEPARTMENT = "department", "Department staff"
        EMERGENCY = "emergency", "Emergency services"
        ADMIN = "admin", "Administrator"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    is_approved = models.BooleanField(
        default=False, help_text="Set by an administrator to acknowledge the registration."
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="approvals"
    )
    rejected = models.BooleanField(default=False)
    phone = models.CharField(max_length=32, blank=True)
    department = models.ForeignKey(
        "clinic.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="staff"
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        full = self.get_full_name().strip()
        return full or self.username

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p]
        return ("".join(p[0] for p in parts) or self.username[:2]).upper()

    def approve(self, by):
        self.is_approved = True
        self.rejected = False
        self.is_active = True
        self.approved_at = timezone.now()
        self.approved_by = by
        self.save(update_fields=["is_approved", "rejected", "is_active", "approved_at", "approved_by"])

    def reject(self, by):
        self.is_approved = False
        self.rejected = True
        self.approved_by = by
        self.save(update_fields=["is_approved", "rejected", "approved_by"])

    # role helpers used throughout templates & permission checks
    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_department(self):
        return self.role == self.Role.DEPARTMENT

    @property
    def is_emergency(self):
        return self.role == self.Role.EMERGENCY

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
            self.is_approved = True
        super().save(*args, **kwargs)

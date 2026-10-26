from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """One user table for all stakeholders. `role` decides what a user can do."""

    PATIENT = "patient"
    DOCTOR = "doctor"
    DEPARTMENT = "department"
    EMERGENCY = "emergency"
    ADMIN = "admin"
    ROLE_CHOICES = [
        (PATIENT, "Patient"),
        (DOCTOR, "Doctor"),
        (DEPARTMENT, "Department staff"),
        (EMERGENCY, "Emergency services"),
        (ADMIN, "Administrator"),
    ]
    DEPARTMENT_CHOICES = [
        ("radiology", "Radiology"),
        ("laboratory", "Laboratory"),
        ("cardiology", "Cardiology"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=PATIENT)
    # Patients and doctors must be acknowledged by an administrator before they can use the system.
    is_approved = models.BooleanField(default=False)
    phone = models.CharField(max_length=30, blank=True)
    specialty = models.CharField(max_length=100, blank=True)  # doctors only
    license_number = models.CharField(max_length=50, blank=True)  # doctors only
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, blank=True)  # department staff only

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ADMIN
            self.is_approved = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username

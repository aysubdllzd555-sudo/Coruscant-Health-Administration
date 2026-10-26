from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import User


class Patient(models.Model):
    """Medical record. Patients who register have a user account;
    patients added by emergency services may not have one."""

    PRIORITY_CHOICES = [("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    full_name = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female"), ("other", "Other")], blank=True)
    blood_type = models.CharField(max_length=5, blank=True)
    allergies = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="patients", limit_choices_to={"role": User.DOCTOR},
    )
    # Emergency intake
    is_emergency = models.BooleanField(default=False)
    complaint = models.CharField(max_length=200, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    def status(self):
        """Compares the last 3 readings with the 3 before them.
        Fewer abnormal values = improving."""
        readings = list(self.readings.all()[:6])
        if len(readings) < 6:
            return "not enough data"
        recent = sum(r.abnormal_count() for r in readings[:3])
        before = sum(r.abnormal_count() for r in readings[3:])
        if recent < before:
            return "improving"
        if recent > before:
            return "worsening"
        return "stable"


class Reading(models.Model):
    """One measurement uploaded from the patient's wearable device."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="readings")
    recorded_at = models.DateTimeField(default=timezone.now)
    heart_rate = models.PositiveIntegerField(help_text="beats per minute")
    systolic = models.PositiveIntegerField(help_text="blood pressure, mmHg")
    diastolic = models.PositiveIntegerField(help_text="blood pressure, mmHg")
    temperature = models.DecimalField(max_digits=4, decimal_places=1, help_text="°C")
    oxygen = models.PositiveIntegerField(help_text="SpO₂ %")

    class Meta:
        ordering = ["-recorded_at"]

    # normal ranges for an adult
    def is_heart_rate_ok(self):
        return 60 <= self.heart_rate <= 100

    def is_pressure_ok(self):
        return 90 <= self.systolic <= 140 and 60 <= self.diastolic <= 90

    def is_temperature_ok(self):
        return 36.0 <= float(self.temperature) <= 37.5

    def is_oxygen_ok(self):
        return self.oxygen >= 95

    def abnormal_count(self):
        checks = [self.is_heart_rate_ok(), self.is_pressure_ok(), self.is_temperature_ok(), self.is_oxygen_ok()]
        return checks.count(False)


class Report(models.Model):
    """Doctor's report: assessment + prescription the patient can read."""

    CONDITION_CHOICES = [("improving", "Improving"), ("stable", "Stable"), ("worsening", "Worsening")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="reports")
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    notes = models.TextField("Assessment")
    prescription = models.TextField("Prescription / suggestions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Order(models.Model):
    """A service the doctor orders from a department (CT scan, blood test...)."""

    SERVICE_CHOICES = [
        ("ct_scan", "CT scan"),
        ("pet_scan", "PET scan"),
        ("mri", "MRI"),
        ("xray", "X-ray"),
        ("blood_test", "Blood test"),
        ("urine_test", "Urine test"),
        ("ecg", "ECG"),
    ]
    # which department executes each service
    SERVICE_DEPARTMENT = {
        "ct_scan": "radiology", "pet_scan": "radiology", "mri": "radiology", "xray": "radiology",
        "blood_test": "laboratory", "urine_test": "laboratory", "ecg": "cardiology",
    }
    STATUS_CHOICES = [("pending", "Pending"), ("in_progress", "In progress"), ("completed", "Completed")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="orders")
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    department = models.CharField(max_length=20, choices=User.DEPARTMENT_CHOICES, editable=False)
    notes = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    result = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.department = self.SERVICE_DEPARTMENT[self.service]
        super().save(*args, **kwargs)


class Document(models.Model):
    """Uploaded file. Only the encrypted bytes are stored in the database."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    title = models.CharField(max_length=120)
    filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=100)
    nonce = models.BinaryField()
    encrypted_data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Message(models.Model):
    """Messages between a patient and the care team."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

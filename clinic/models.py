import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from . import scoring

User = settings.AUTH_USER_MODEL

DISTRICTS = [
    ("galactic_city", "Galactic City"),
    ("senate", "Senate District"),
    ("manarai", "Manarai Heights"),
    ("uscru", "Uscru Entertainment District"),
    ("coco_town", "Coco Town"),
    ("the_works", "The Works"),
    ("level_1313", "Level 1313"),
    ("offworld", "Off-world / traveller"),
]


class Department(models.Model):
    class Kind(models.TextChoices):
        IMAGING = "imaging", "Imaging"
        LAB = "lab", "Laboratory"
        CARDIO = "cardio", "Cardiology"
        PHARMACY = "pharmacy", "Pharmacy"
        OTHER = "other", "Other"

    name = models.CharField(max_length=80, unique=True)
    code = models.SlugField(max_length=16, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)
    location = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ServiceType(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=24, unique=True)
    target_minutes = models.PositiveIntegerField(default=60, help_text="Turnaround target for routine orders")

    class Meta:
        ordering = ["department__name", "name"]

    def __str__(self):
        return self.name


def new_mrn():
    return f"CHA-{secrets.randbelow(10**7):07d}"


class Patient(models.Model):
    class Sex(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        OTHER = "X", "Other / unknown"

    class Source(models.TextChoices):
        REGISTRATION = "registration", "Self-registration"
        EMERGENCY = "emergency", "Emergency intake"
        ADMIN = "admin", "Administrator"

    class EDStatus(models.TextChoices):
        NONE = "none", "Not in ED"
        INBOUND = "inbound", "Inbound"
        WAITING = "waiting", "Waiting"
        IN_BAY = "in_bay", "In bay"
        DISCHARGED = "discharged", "Discharged"
        ADMITTED = "admitted", "Admitted"

    class Acuity(models.IntegerChoices):
        ESI1 = 1, "1 · Resuscitation"
        ESI2 = 2, "2 · Emergent"
        ESI3 = 3, "3 · Urgent"
        ESI4 = 4, "4 · Less urgent"
        ESI5 = 5, "5 · Non-urgent"

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="patient")
    mrn = models.CharField("MRN", max_length=20, unique=True, default=new_mrn)
    first_name = models.CharField(max_length=60, blank=True)
    last_name = models.CharField(max_length=60, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    approx_age = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=Sex.choices, default=Sex.OTHER)
    species = models.CharField(max_length=40, default="Human")
    blood_type = models.CharField(max_length=4, blank=True)
    allergies = models.CharField(max_length=200, blank=True)
    district = models.CharField(max_length=20, choices=DISTRICTS, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    emergency_contact = models.CharField(max_length=120, blank=True)
    primary_doctor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_patients",
        limit_choices_to={"role": "doctor"},
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.REGISTRATION)
    is_unidentified = models.BooleanField(default=False)

    # Emergency department tracking
    ed_status = models.CharField(max_length=12, choices=EDStatus.choices, default=EDStatus.NONE)
    acuity = models.PositiveSmallIntegerField(choices=Acuity.choices, null=True, blank=True)
    chief_complaint = models.CharField(max_length=120, blank=True)
    arrival_mode = models.CharField(max_length=20, blank=True)
    bay = models.CharField(max_length=8, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    brainworm_screened = models.BooleanField(default=False)
    vaccinated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.display_name} ({self.mrn})"

    @property
    def display_name(self):
        if self.is_unidentified and not (self.first_name or self.last_name):
            return f"Unidentified {self.get_sex_display().split()[0]}"
        return f"{self.last_name.upper()}, {self.first_name}".strip(", ") or self.mrn

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.localdate()
            dob = self.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return self.approx_age

    @property
    def minutes_in_ed(self):
        if self.arrived_at and self.ed_status in {self.EDStatus.WAITING, self.EDStatus.IN_BAY}:
            return int((timezone.now() - self.arrived_at).total_seconds() // 60)
        return None

    def recent_readings(self, n=20):
        return list(self.readings.order_by("-recorded_at")[:n])

    @property
    def latest_reading(self):
        return self.readings.order_by("-recorded_at").first()

    @property
    def trend(self):
        return scoring.trend(self.recent_readings(10))

    def can_be_viewed_by(self, user):
        if not user.is_authenticated or not (user.is_approved or user.is_superuser):
            return False
        if user.is_admin_role or user.is_doctor or user.is_emergency:
            return True
        if user.is_patient:
            return self.user_id == user.id
        if user.is_department:
            return self.orders.filter(service__department_id=user.department_id).exists()
        return False


class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="doctor_profile")
    specialty = models.CharField(max_length=80, blank=True)
    license_number = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f"Dr. {self.user.display_name}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Device(models.Model):
    class Kind(models.TextChoices):
        WEARABLE = "wearable", "Wearable vital monitor"
        PATCH = "patch", "Cardiac patch"
        GLUCOSE = "glucose", "Continuous glucose monitor"
        OXIMETER = "oximeter", "Pulse oximeter"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="devices")
    label = models.CharField(max_length=60)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.WEARABLE)
    serial = models.CharField(max_length=40, blank=True)
    token_prefix = models.CharField(max_length=12, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.label} · {self.patient.mrn}"

    def issue_token(self) -> str:
        """Generates a new API token; only its hash is stored. Returns the clear token once."""
        token = "dev_" + secrets.token_urlsafe(32)
        self.token_prefix = token[:10]
        self.token_hash = _hash_token(token)
        return token

    @classmethod
    def authenticate(cls, token: str):
        if not token:
            return None
        return cls.objects.select_related("patient").filter(token_hash=_hash_token(token), active=True).first()


class Reading(models.Model):
    class Source(models.TextChoices):
        DEVICE = "device", "Device"
        UPLOAD = "upload", "File upload"
        MANUAL = "manual", "Manual entry"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="readings")
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL, related_name="readings")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.DEVICE)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    heart_rate = models.PositiveSmallIntegerField("Heart rate (bpm)", null=True, blank=True)
    spo2 = models.PositiveSmallIntegerField("SpO₂ (%)", null=True, blank=True)
    temperature_c = models.DecimalField("Temperature (°C)", max_digits=4, decimal_places=1, null=True, blank=True)
    systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    resp_rate = models.PositiveSmallIntegerField("Respiratory rate", null=True, blank=True)
    glucose = models.DecimalField("Glucose (mmol/L)", max_digits=4, decimal_places=1, null=True, blank=True)
    steps = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["patient", "-recorded_at"])]

    def __str__(self):
        return f"{self.patient.mrn} @ {self.recorded_at:%Y-%m-%d %H:%M}"

    @property
    def news2(self):
        return scoring.news2(self)

    @property
    def risk(self):
        return scoring.risk_level(self.news2)


class Report(models.Model):
    class Trend(models.TextChoices):
        IMPROVING = "improving", "Improving"
        STABLE = "stable", "Stable"
        WORSENING = "worsening", "Worsening"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="reports")
    doctor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reports")
    title = models.CharField(max_length=120)
    assessment = models.TextField(help_text="Clinical findings and interpretation of the readings")
    suggestions = models.TextField(help_text="Prescription, lifestyle advice and next steps — visible to the patient")
    condition = models.CharField(max_length=10, choices=Trend.choices, default=Trend.STABLE)
    follow_up_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_patient_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Order(models.Model):
    class Priority(models.TextChoices):
        STAT = "stat", "STAT"
        URGENT = "urgent", "Urgent"
        ROUTINE = "routine", "Routine"

    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        ACCEPTED = "accepted", "Accepted"
        IN_PROGRESS = "in_progress", "In progress"
        RESULTED = "resulted", "Resulted"
        CANCELLED = "cancelled", "Cancelled"

    class Flag(models.TextChoices):
        NORMAL = "normal", "Normal"
        ABNORMAL = "abnormal", "Abnormal"
        CRITICAL = "critical", "Critical"

    NEXT_STATUS = {Status.ORDERED: Status.ACCEPTED, Status.ACCEPTED: Status.IN_PROGRESS}

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="orders")
    service = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="orders")
    ordered_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders_placed")
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.ROUTINE)
    indication = models.CharField("Clinical indication", max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ORDERED, db_index=True)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders_assigned")
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    resulted_at = models.DateTimeField(null=True, blank=True)
    result_summary = models.TextField(blank=True)
    result_flag = models.CharField(max_length=10, choices=Flag.choices, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.service} for {self.patient.mrn}"

    @property
    def department(self):
        return self.service.department

    @property
    def is_open(self):
        return self.status in {self.Status.ORDERED, self.Status.ACCEPTED, self.Status.IN_PROGRESS}

    @property
    def age_minutes(self):
        end = self.resulted_at or timezone.now()
        return int((end - self.created_at).total_seconds() // 60)

    def advance(self, user):
        nxt = self.NEXT_STATUS.get(self.status)
        if not nxt:
            return False
        now = timezone.now()
        if nxt == self.Status.ACCEPTED:
            self.accepted_at, self.assigned_to = now, user
        else:
            self.started_at = now
        self.status = nxt
        self.save()
        return True

    def record_result(self, user, summary, flag):
        self.result_summary, self.result_flag = summary, flag
        self.status = self.Status.RESULTED
        self.resulted_at = timezone.now()
        self.assigned_to = self.assigned_to or user
        self.started_at = self.started_at or self.resulted_at
        self.accepted_at = self.accepted_at or self.resulted_at
        self.save()


class Document(models.Model):
    """A file stored only as AES-256-GCM ciphertext (see clinic/crypto.py)."""

    class Category(models.TextChoices):
        LAB = "lab", "Lab result"
        IMAGING = "imaging", "Imaging"
        REFERRAL = "referral", "Referral / letter"
        PRESCRIPTION = "prescription", "Prescription"
        INSURANCE = "insurance", "Insurance / ID"
        OTHER = "other", "Other"

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="documents_uploaded")
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    category = models.CharField(max_length=14, choices=Category.choices, default=Category.OTHER)
    title = models.CharField(max_length=120)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    key_id = models.CharField(max_length=32)
    wrapped_key = models.BinaryField()
    nonce = models.BinaryField()
    ciphertext = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def aad(self):
        return self.uid.bytes

    @classmethod
    def seal(cls, *, data: bytes, **fields):
        from . import crypto

        doc = cls(**fields)
        sealed = crypto.encrypt_bytes(data, doc.aad)
        doc.size = len(data)
        doc.sha256 = sealed.sha256
        doc.key_id = sealed.key_id
        doc.wrapped_key = sealed.wrapped_key
        doc.nonce = sealed.nonce
        doc.ciphertext = sealed.ciphertext
        doc.save()
        return doc

    def decrypt(self) -> bytes:
        from . import crypto

        data = crypto.decrypt_bytes(self.key_id, self.wrapped_key, self.nonce, self.ciphertext, self.aad)
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise ValueError("Integrity check failed")
        return data

    def rewrap(self):
        """Re-wraps the DEK with the current active master key (key rotation)."""
        from . import crypto

        dek = crypto.unwrap_key(self.key_id, self.wrapped_key, self.aad)
        self.key_id, self.wrapped_key = crypto.wrap_key(dek, self.aad)
        self.save(update_fields=["key_id", "wrapped_key"])

    def can_be_viewed_by(self, user):
        if self.patient.can_be_viewed_by(user):
            if user.is_department:
                return self.order is not None and self.order.service.department_id == user.department_id
            return True
        return False


class Message(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.PROTECT, related_name="messages_sent")
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField(max_length=40, db_index=True)
    target = models.CharField(max_length=120, blank=True)
    patient = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    ip = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at"]

    @classmethod
    def log(cls, request, action, target="", patient=None):
        user = getattr(request, "user", None)
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip() or None
        return cls.objects.create(
            actor=user if user and user.is_authenticated else None,
            action=action, target=str(target)[:120], patient=patient, ip=ip,
        )

import clinic.models
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=80, unique=True)),
                ("code", models.SlugField(max_length=16, unique=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("imaging", "Imaging"),
                            ("lab", "Laboratory"),
                            ("cardio", "Cardiology"),
                            ("pharmacy", "Pharmacy"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=16,
                    ),
                ),
                ("location", models.CharField(blank=True, max_length=80)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="DoctorProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("specialty", models.CharField(blank=True, max_length=80)),
                ("license_number", models.CharField(blank=True, max_length=40)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="doctor_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Patient",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "mrn",
                    models.CharField(
                        default=clinic.models.new_mrn,
                        max_length=20,
                        unique=True,
                        verbose_name="MRN",
                    ),
                ),
                ("first_name", models.CharField(blank=True, max_length=60)),
                ("last_name", models.CharField(blank=True, max_length=60)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("approx_age", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "sex",
                    models.CharField(
                        choices=[
                            ("F", "Female"),
                            ("M", "Male"),
                            ("X", "Other / unknown"),
                        ],
                        default="X",
                        max_length=1,
                    ),
                ),
                ("species", models.CharField(default="Human", max_length=40)),
                ("blood_type", models.CharField(blank=True, max_length=4)),
                ("allergies", models.CharField(blank=True, max_length=200)),
                (
                    "district",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("galactic_city", "Galactic City"),
                            ("senate", "Senate District"),
                            ("manarai", "Manarai Heights"),
                            ("uscru", "Uscru Entertainment District"),
                            ("coco_town", "Coco Town"),
                            ("the_works", "The Works"),
                            ("level_1313", "Level 1313"),
                            ("offworld", "Off-world / traveller"),
                        ],
                        max_length=20,
                    ),
                ),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("emergency_contact", models.CharField(blank=True, max_length=120)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("registration", "Self-registration"),
                            ("emergency", "Emergency intake"),
                            ("admin", "Administrator"),
                        ],
                        default="registration",
                        max_length=16,
                    ),
                ),
                ("is_unidentified", models.BooleanField(default=False)),
                (
                    "ed_status",
                    models.CharField(
                        choices=[
                            ("none", "Not in ED"),
                            ("inbound", "Inbound"),
                            ("waiting", "Waiting"),
                            ("in_bay", "In bay"),
                            ("discharged", "Discharged"),
                            ("admitted", "Admitted"),
                        ],
                        default="none",
                        max_length=12,
                    ),
                ),
                (
                    "acuity",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "1 · Resuscitation"),
                            (2, "2 · Emergent"),
                            (3, "3 · Urgent"),
                            (4, "4 · Less urgent"),
                            (5, "5 · Non-urgent"),
                        ],
                        null=True,
                    ),
                ),
                ("chief_complaint", models.CharField(blank=True, max_length=120)),
                ("arrival_mode", models.CharField(blank=True, max_length=20)),
                ("bay", models.CharField(blank=True, max_length=8)),
                ("arrived_at", models.DateTimeField(blank=True, null=True)),
                ("brainworm_screened", models.BooleanField(default=False)),
                ("vaccinated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "primary_doctor",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"role": "doctor"},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="primary_patients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="patient",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["last_name", "first_name"],
            },
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("stat", "STAT"),
                            ("urgent", "Urgent"),
                            ("routine", "Routine"),
                        ],
                        default="routine",
                        max_length=8,
                    ),
                ),
                (
                    "indication",
                    models.CharField(
                        max_length=200, verbose_name="Clinical indication"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ordered", "Ordered"),
                            ("accepted", "Accepted"),
                            ("in_progress", "In progress"),
                            ("resulted", "Resulted"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="ordered",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("resulted_at", models.DateTimeField(blank=True, null=True)),
                ("result_summary", models.TextField(blank=True)),
                (
                    "result_flag",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("normal", "Normal"),
                            ("abnormal", "Abnormal"),
                            ("critical", "Critical"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="orders_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ordered_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders_placed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orders",
                        to="clinic.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("body", models.TextField(max_length=4000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="messages_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="clinic.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "uid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("lab", "Lab result"),
                            ("imaging", "Imaging"),
                            ("referral", "Referral / letter"),
                            ("prescription", "Prescription"),
                            ("insurance", "Insurance / ID"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=14,
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                ("original_name", models.CharField(max_length=200)),
                ("content_type", models.CharField(max_length=100)),
                ("size", models.PositiveIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("key_id", models.CharField(max_length=32)),
                ("wrapped_key", models.BinaryField()),
                ("nonce", models.BinaryField()),
                ("ciphertext", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents_uploaded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="clinic.order",
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="clinic.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Device",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("label", models.CharField(max_length=60)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("wearable", "Wearable vital monitor"),
                            ("patch", "Cardiac patch"),
                            ("glucose", "Continuous glucose monitor"),
                            ("oximeter", "Pulse oximeter"),
                        ],
                        default="wearable",
                        max_length=16,
                    ),
                ),
                ("serial", models.CharField(blank=True, max_length=40)),
                ("token_prefix", models.CharField(editable=False, max_length=12)),
                (
                    "token_hash",
                    models.CharField(editable=False, max_length=64, unique=True),
                ),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="devices",
                        to="clinic.patient",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("action", models.CharField(db_index=True, max_length=40)),
                ("target", models.CharField(blank=True, max_length=120)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to="clinic.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["-at"],
            },
        ),
        migrations.CreateModel(
            name="Report",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                (
                    "assessment",
                    models.TextField(
                        help_text="Clinical findings and interpretation of the readings"
                    ),
                ),
                (
                    "suggestions",
                    models.TextField(
                        help_text="Prescription, lifestyle advice and next steps — visible to the patient"
                    ),
                ),
                (
                    "condition",
                    models.CharField(
                        choices=[
                            ("improving", "Improving"),
                            ("stable", "Stable"),
                            ("worsening", "Worsening"),
                        ],
                        default="stable",
                        max_length=10,
                    ),
                ),
                ("follow_up_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_by_patient_at", models.DateTimeField(blank=True, null=True)),
                (
                    "doctor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="clinic.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ServiceType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("code", models.SlugField(max_length=24, unique=True)),
                (
                    "target_minutes",
                    models.PositiveIntegerField(
                        default=60, help_text="Turnaround target for routine orders"
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="services",
                        to="clinic.department",
                    ),
                ),
            ],
            options={
                "ordering": ["department__name", "name"],
            },
        ),
        migrations.AddField(
            model_name="order",
            name="service",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to="clinic.servicetype",
            ),
        ),
        migrations.CreateModel(
            name="Reading",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("device", "Device"),
                            ("upload", "File upload"),
                            ("manual", "Manual entry"),
                        ],
                        default="device",
                        max_length=10,
                    ),
                ),
                (
                    "recorded_at",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now
                    ),
                ),
                (
                    "heart_rate",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="Heart rate (bpm)"
                    ),
                ),
                (
                    "spo2",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="SpO₂ (%)"
                    ),
                ),
                (
                    "temperature_c",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=4,
                        null=True,
                        verbose_name="Temperature (°C)",
                    ),
                ),
                ("systolic", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("diastolic", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "resp_rate",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="Respiratory rate"
                    ),
                ),
                (
                    "glucose",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=4,
                        null=True,
                        verbose_name="Glucose (mmol/L)",
                    ),
                ),
                ("steps", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "device",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="readings",
                        to="clinic.device",
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="readings",
                        to="clinic.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at"],
                "indexes": [
                    models.Index(
                        fields=["patient", "-recorded_at"],
                        name="clinic_read_patient_d4700c_idx",
                    )
                ],
            },
        ),
    ]

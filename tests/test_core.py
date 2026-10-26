import json
from decimal import Decimal

from cryptography.exceptions import InvalidTag
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from clinic import crypto, ingest, scoring
from clinic.models import AuditEvent, Department, Device, Document, Order, Patient, Reading, Report, ServiceType

PW = "Str0ng-Passw0rd!"
PDF = b"%PDF-1.4\n% test document\n%%EOF"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_cha", verbosity=0)
        cls.admin = User.objects.create_user("admin", password=PW, role=User.Role.ADMIN, is_approved=True)
        cls.doctor = User.objects.create_user("doc", password=PW, role=User.Role.DOCTOR, is_approved=True, first_name="Ana", last_name="Venn")
        cls.imaging = Department.objects.get(code="imaging")
        cls.lab = Department.objects.get(code="lab")
        cls.tech = User.objects.create_user("tech", password=PW, role=User.Role.DEPARTMENT, is_approved=True, department=cls.imaging)
        cls.labtech = User.objects.create_user("labtech", password=PW, role=User.Role.DEPARTMENT, is_approved=True, department=cls.lab)
        cls.medic = User.objects.create_user("medic", password=PW, role=User.Role.EMERGENCY, is_approved=True)
        cls.pu = User.objects.create_user("pat", password=PW, role=User.Role.PATIENT, is_approved=True, first_name="Josh", last_name="Marvel")
        cls.patient = Patient.objects.create(user=cls.pu, first_name="Josh", last_name="Marvel", date_of_birth="1967-08-01", primary_doctor=cls.doctor)
        cls.other_u = User.objects.create_user("other", password=PW, role=User.Role.PATIENT, is_approved=True)
        cls.other = Patient.objects.create(user=cls.other_u, first_name="Sela", last_name="Dray")
        cls.ct = ServiceType.objects.get(code="ct-head")

    def login(self, user):
        self.client.force_login(user)


# ---------------------------------------------------------------- scoring

class ScoringTests(TestCase):
    def r(self, **kw):
        return Reading(**kw)

    def test_news2_normal_is_zero(self):
        self.assertEqual(scoring.news2(self.r(heart_rate=70, spo2=98, resp_rate=14, systolic=120, temperature_c=Decimal("36.8"))), 0)

    def test_news2_high_risk(self):
        s = scoring.news2(self.r(heart_rate=135, spo2=88, resp_rate=26, systolic=88, temperature_c=Decimal("39.5")))
        self.assertEqual(s, 3 + 3 + 3 + 3 + 2)
        self.assertEqual(scoring.risk_level(s), "high")

    def test_news2_none_without_data(self):
        self.assertIsNone(scoring.news2(self.r()))
        self.assertEqual(scoring.risk_level(None), "unknown")

    def test_trend_directions(self):
        sick = [self.r(heart_rate=135, spo2=88, resp_rate=26) for _ in range(5)]
        well = [self.r(heart_rate=70, spo2=98, resp_rate=14) for _ in range(5)]
        self.assertEqual(scoring.trend(well + sick), scoring.TREND_IMPROVING)   # newest first
        self.assertEqual(scoring.trend(sick + well), scoring.TREND_WORSENING)
        self.assertEqual(scoring.trend(well + well), scoring.TREND_STABLE)
        self.assertEqual(scoring.trend(well[:1]), scoring.TREND_UNKNOWN)


# ---------------------------------------------------------------- crypto

class CryptoTests(Base):
    def test_roundtrip_and_ciphertext_differs(self):
        doc = Document.seal(data=PDF, patient=self.patient, uploaded_by=self.doctor, title="t", original_name="a.pdf", content_type="application/pdf")
        doc.refresh_from_db()
        self.assertNotIn(b"test document", bytes(doc.ciphertext))
        self.assertEqual(doc.decrypt(), PDF)
        self.assertEqual(len(bytes(doc.nonce)), 12)

    def test_tamper_detected(self):
        doc = Document.seal(data=PDF, patient=self.patient, uploaded_by=self.doctor, title="t", original_name="a.pdf", content_type="application/pdf")
        ct = bytearray(doc.ciphertext)
        ct[0] ^= 1
        doc.ciphertext = bytes(ct)
        with self.assertRaises(InvalidTag):
            doc.decrypt()

    def test_ciphertext_bound_to_document(self):
        a = Document.seal(data=PDF, patient=self.patient, uploaded_by=self.doctor, title="a", original_name="a.pdf", content_type="application/pdf")
        b = Document.seal(data=b"%PDF other", patient=self.patient, uploaded_by=self.doctor, title="b", original_name="b.pdf", content_type="application/pdf")
        b.wrapped_key, b.nonce, b.ciphertext = a.wrapped_key, a.nonce, a.ciphertext
        with self.assertRaises(InvalidTag):
            b.decrypt()

    def test_key_rotation(self):
        k1, k2 = crypto.generate_master_key(), crypto.generate_master_key()
        with override_settings(DOCUMENT_MASTER_KEYS=f"k1:{k1}"):
            doc = Document.seal(data=PDF, patient=self.patient, uploaded_by=self.doctor, title="t", original_name="a.pdf", content_type="application/pdf")
        with override_settings(DOCUMENT_MASTER_KEYS=f"k2:{k2},k1:{k1}"):
            call_command("rotate_document_keys", verbosity=0)
            doc.refresh_from_db()
            self.assertEqual(doc.key_id, "k2")
        with override_settings(DOCUMENT_MASTER_KEYS=f"k2:{k2}"):  # old key retired
            self.assertEqual(doc.decrypt(), PDF)


# ---------------------------------------------------------------- registration & approval

class RegistrationTests(Base):
    def test_patient_registers_and_waits_for_approval(self):
        r = self.client.post(reverse("accounts:register"), {
            "role": "patient", "username": "newpat", "first_name": "Iri", "last_name": "Tal", "email": "iri@example.com",
            "date_of_birth": "1990-01-02", "sex": "F", "district": "manarai", "password1": PW, "password2": PW})
        self.assertRedirects(r, reverse("accounts:pending"))
        u = User.objects.get(username="newpat")
        self.assertFalse(u.is_approved)
        self.assertTrue(Patient.objects.filter(user=u, district="manarai").exists())
        self.assertRedirects(self.client.get(reverse("clinic:my_dashboard")), reverse("accounts:pending"))

    def test_doctor_requires_licence(self):
        r = self.client.post(reverse("accounts:register"), {
            "role": "doctor", "username": "newdoc", "first_name": "A", "last_name": "B", "email": "d@example.com",
            "password1": PW, "password2": PW})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="newdoc").exists())

    def test_admin_approves(self):
        u = User.objects.create_user("pending", password=PW, role=User.Role.DOCTOR)
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("accounts:approvals")), "pending")
        self.client.post(reverse("accounts:decide", args=[u.pk]), {"decision": "approve"})
        u.refresh_from_db()
        self.assertTrue(u.is_approved)
        self.assertEqual(u.approved_by, self.admin)

    def test_non_admin_cannot_approve(self):
        u = User.objects.create_user("pending", password=PW, role=User.Role.DOCTOR)
        self.login(self.doctor)
        self.assertEqual(self.client.post(reverse("accounts:decide", args=[u.pk]), {"decision": "approve"}).status_code, 403)
        u.refresh_from_db()
        self.assertFalse(u.is_approved)


# ---------------------------------------------------------------- patient & device data

class PatientDataTests(Base):
    def test_csv_upload(self):
        self.login(self.pu)
        csv = b"recorded_at,heart_rate,spo2,temp\n2026-01-01T08:00:00Z,72,98,36.8\n2026-01-01T09:00:00Z,80,97,37.0\n"
        self.client.post(reverse("clinic:upload_readings"), {"file": SimpleUploadedFile("export.csv", csv)})
        self.assertEqual(self.patient.readings.count(), 2)
        self.assertEqual(self.patient.readings.first().source, "upload")

    def test_upload_rejects_out_of_range(self):
        with self.assertRaises(ingest.IngestError):
            ingest.parse_rows([{"heart_rate": 900}])
        with self.assertRaises(ingest.IngestError):
            ingest.parse_rows([{"notes": "hello"}])

    def test_device_api(self):
        dev = Device(patient=self.patient, label="Band")
        token = dev.issue_token()
        dev.save()
        self.assertNotIn(token, dev.token_hash)
        url = reverse("clinic:api_readings")
        body = json.dumps({"readings": [{"heart_rate": 140, "spo2": 89, "resp_rate": 26}]})
        r = self.client.post(url, body, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(r.status_code, 201)
        self.assertGreaterEqual(r.json()["latest_news2"], 7)
        self.assertEqual(self.client.post(url, body, content_type="application/json", HTTP_AUTHORIZATION="Bearer nope").status_code, 401)
        dev.active = False
        dev.save()
        self.assertEqual(self.client.post(url, body, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").status_code, 401)

    def test_patient_sees_only_own_data(self):
        self.login(self.pu)
        self.assertEqual(self.client.get(reverse("clinic:my_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("clinic:api_patient_readings", args=[self.other.mrn])).status_code, 403)
        self.assertEqual(self.client.get(reverse("clinic:worklist")).status_code, 403)

    def test_patient_reads_doctor_suggestions(self):
        Report.objects.create(patient=self.patient, doctor=self.doctor, title="Plan", assessment="ok", suggestions="Drink water")
        self.login(self.pu)
        self.assertContains(self.client.get(reverse("clinic:my_reports")), "Drink water")
        self.assertIsNotNone(self.patient.reports.first().read_by_patient_at)


# ---------------------------------------------------------------- doctor workflow

class DoctorTests(Base):
    def test_worklist_and_chart(self):
        Reading.objects.create(patient=self.patient, heart_rate=135, spo2=88, resp_rate=26)
        self.login(self.doctor)
        r = self.client.get(reverse("clinic:worklist"))
        self.assertContains(r, "MARVEL")
        self.assertEqual(r.context["summary"]["high"], 1)
        self.assertEqual(self.client.get(reverse("clinic:patient_chart", args=[self.patient.mrn])).status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action="view_chart", patient=self.patient).exists())

    def test_write_report(self):
        self.login(self.doctor)
        self.client.post(reverse("clinic:write_report", args=[self.patient.mrn]), {
            "title": "Review", "condition": "improving", "assessment": "Better", "suggestions": "Rest"})
        self.assertEqual(self.patient.reports.get().condition, "improving")

    def test_place_order(self):
        self.login(self.doctor)
        self.client.post(reverse("clinic:place_order", args=[self.patient.mrn]), {"service": self.ct.pk, "priority": "stat", "indication": "Headache"})
        o = Order.objects.get()
        self.assertEqual((o.status, o.priority, o.department), ("ordered", "stat", self.imaging))

    def test_patient_cannot_write_report(self):
        self.login(self.pu)
        r = self.client.post(reverse("clinic:write_report", args=[self.patient.mrn]), {"title": "x", "condition": "stable", "assessment": "x", "suggestions": "x"})
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------- department workflow

class DepartmentTests(Base):
    def setUp(self):
        self.order = Order.objects.create(patient=self.patient, service=self.ct, ordered_by=self.doctor, priority="stat", indication="Head injury")

    def test_queue_and_full_lifecycle(self):
        self.login(self.tech)
        self.assertContains(self.client.get(reverse("clinic:department_queue")), "Head injury")
        self.client.post(reverse("clinic:advance_order", args=[self.order.pk]))
        self.client.post(reverse("clinic:advance_order", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "in_progress")
        self.client.post(reverse("clinic:result_order", args=[self.order.pk]), {
            "result_flag": "abnormal", "result_summary": "Small subdural haematoma",
            "file": SimpleUploadedFile("ct.pdf", PDF, content_type="application/pdf")})
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.result_flag), ("resulted", "abnormal"))
        doc = self.order.documents.get()
        self.assertEqual(doc.decrypt(), PDF)

    def test_other_department_cannot_touch_order(self):
        self.login(self.labtech)
        self.assertEqual(self.client.post(reverse("clinic:advance_order", args=[self.order.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse("clinic:department_queue")), "Head injury")


# ---------------------------------------------------------------- emergency

class EmergencyTests(Base):
    def test_rapid_intake_unknown_patient(self):
        self.login(self.medic)
        r = self.client.post(reverse("clinic:ed_intake"), {"chief_complaint": "Unresponsive", "acuity": 1, "sex": "M", "species": "Human",
                                                            "arrival_mode": "ambulance", "bay": "a2", "heart_rate": 130, "spo2": 85})
        self.assertRedirects(r, reverse("clinic:ed_board"))
        p = Patient.objects.get(chief_complaint="Unresponsive")
        self.assertTrue(p.is_unidentified)
        self.assertEqual((p.bay, p.ed_status, p.acuity), ("A2", "in_bay", 1))
        self.assertTrue(p.mrn.startswith("CHA-"))
        self.assertEqual(p.readings.get().spo2, 85)
        self.assertContains(self.client.get(reverse("clinic:ed_board")), "Unidentified")

    def test_intake_requires_only_complaint_and_acuity(self):
        self.login(self.medic)
        self.client.post(reverse("clinic:ed_intake"), {"chief_complaint": "Fever", "acuity": 4, "sex": "X", "species": "Twi'lek", "arrival_mode": "walk_in"})
        self.assertEqual(Patient.objects.get(chief_complaint="Fever").ed_status, "waiting")

    def test_occupied_bay_rejected(self):
        Patient.objects.create(chief_complaint="x", bay="A1", ed_status="in_bay", arrived_at=timezone.now())
        self.login(self.medic)
        r = self.client.post(reverse("clinic:ed_intake"), {"chief_complaint": "Second", "acuity": 3, "sex": "X", "species": "Human", "arrival_mode": "walk_in", "bay": "A1"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Patient.objects.filter(chief_complaint="Second").exists())


# ---------------------------------------------------------------- documents

class DocumentTests(Base):
    def test_patient_upload_and_download(self):
        self.login(self.pu)
        self.client.post(reverse("clinic:upload_document", args=[self.patient.mrn]),
                         {"title": "Insurance card", "category": "insurance", "file": SimpleUploadedFile("card.pdf", PDF, content_type="application/pdf")})
        doc = self.patient.documents.get()
        r = self.client.get(reverse("clinic:download_document", args=[doc.uid]))
        self.assertEqual(r.content, PDF)
        self.assertEqual(r["Cache-Control"], "no-store, private")
        self.assertTrue(AuditEvent.objects.filter(action="download_document").exists())

    def test_other_patient_denied(self):
        doc = Document.seal(data=PDF, patient=self.patient, uploaded_by=self.doctor, title="t", original_name="a.pdf", content_type="application/pdf")
        self.login(self.other_u)
        self.assertEqual(self.client.get(reverse("clinic:download_document", args=[doc.uid])).status_code, 403)

    def test_spoofed_file_type_rejected(self):
        self.login(self.pu)
        self.client.post(reverse("clinic:upload_document", args=[self.patient.mrn]),
                         {"title": "x", "category": "other", "file": SimpleUploadedFile("evil.pdf", b"MZ\x90\x00binary")})
        self.client.post(reverse("clinic:upload_document", args=[self.patient.mrn]),
                         {"title": "x", "category": "other", "file": SimpleUploadedFile("evil.exe", b"MZ")})
        self.assertEqual(self.patient.documents.count(), 0)


# ---------------------------------------------------------------- platform

class PlatformTests(Base):
    def test_healthz(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.json()["status"], "ok")

    def test_security_headers(self):
        r = self.client.get(reverse("accounts:login"))
        self.assertIn("default-src 'self'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")

    def test_monitor_admin_only(self):
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("accounts:monitor")), "Up to date")
        self.login(self.doctor)
        self.assertEqual(self.client.get(reverse("accounts:monitor")).status_code, 403)

    def test_demo_seed(self):
        call_command("seed_cha", demo=True, verbosity=0)
        self.assertTrue(Patient.objects.filter(mrn="CHA-0335227").exists())
        self.assertGreater(Reading.objects.count(), 50)

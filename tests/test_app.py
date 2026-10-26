from cryptography.exceptions import InvalidTag
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from clinic import encryption
from clinic.models import Document, Order, Patient, Reading, Report

PASSWORD = "Test-pass-123"


class BaseTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password=PASSWORD, role=User.ADMIN, is_approved=True)
        self.doctor = User.objects.create_user("doc", password=PASSWORD, role=User.DOCTOR, is_approved=True)
        self.lab = User.objects.create_user("lab", password=PASSWORD, role=User.DEPARTMENT, department="laboratory", is_approved=True)
        self.radiology = User.objects.create_user("rad", password=PASSWORD, role=User.DEPARTMENT, department="radiology", is_approved=True)
        self.medic = User.objects.create_user("medic", password=PASSWORD, role=User.EMERGENCY, is_approved=True)
        self.patient_user = User.objects.create_user("pat", password=PASSWORD, role=User.PATIENT, is_approved=True)
        self.patient = Patient.objects.create(user=self.patient_user, full_name="Josh Marvel")
        other_user = User.objects.create_user("other", password=PASSWORD, role=User.PATIENT, is_approved=True)
        self.other_patient = Patient.objects.create(user=other_user, full_name="Sela Dray")
        self.other_user = other_user


class RegistrationTests(BaseTest):
    def test_patient_registration_needs_approval(self):
        self.client.post(reverse("register"), {
            "username": "newpatient", "first_name": "Iri", "last_name": "Tal", "email": "iri@test.com",
            "role": "patient", "password1": "Very-secret-99", "password2": "Very-secret-99"})
        user = User.objects.get(username="newpatient")
        self.assertFalse(user.is_approved)
        self.assertTrue(Patient.objects.filter(user=user).exists())
        # not approved yet -> redirected to the waiting page
        self.assertRedirects(self.client.get(reverse("patient_home")), reverse("pending"))

    def test_doctor_needs_license_number(self):
        self.client.post(reverse("register"), {
            "username": "newdoc", "role": "doctor", "password1": "Very-secret-99", "password2": "Very-secret-99"})
        self.assertFalse(User.objects.filter(username="newdoc").exists())

    def test_admin_approves_user(self):
        user = User.objects.create_user("waiting", password=PASSWORD, role=User.DOCTOR)
        self.client.force_login(self.admin)
        self.client.post(reverse("approve_user", args=[user.id]), {"action": "approve"})
        user.refresh_from_db()
        self.assertTrue(user.is_approved)

    def test_only_admin_can_approve(self):
        user = User.objects.create_user("waiting", password=PASSWORD, role=User.DOCTOR)
        self.client.force_login(self.doctor)
        response = self.client.post(reverse("approve_user", args=[user.id]), {"action": "approve"})
        self.assertEqual(response.status_code, 403)


class PatientTests(BaseTest):
    def test_add_reading(self):
        self.client.force_login(self.patient_user)
        self.client.post(reverse("add_reading"), {"recorded_at": "2026-10-01T10:00", "heart_rate": 80,
                                                  "systolic": 120, "diastolic": 80, "temperature": "36.6", "oxygen": 98})
        self.assertEqual(self.patient.readings.count(), 1)

    def test_upload_device_csv(self):
        self.client.force_login(self.patient_user)
        csv = (b"recorded_at,heart_rate,systolic,diastolic,temperature,oxygen\n"
               b"2026-10-01T08:00:00,72,120,80,36.6,98\n2026-10-01T09:00:00,110,150,95,38.5,92\n")
        self.client.post(reverse("upload_csv"), {"file": SimpleUploadedFile("device.csv", csv)})
        self.assertEqual(self.patient.readings.count(), 2)

    def test_bad_csv_is_rejected(self):
        self.client.force_login(self.patient_user)
        self.client.post(reverse("upload_csv"), {"file": SimpleUploadedFile("device.csv", b"a,b\n1,2\n")})
        self.assertEqual(self.patient.readings.count(), 0)

    def test_patient_sees_doctor_suggestions(self):
        Report.objects.create(patient=self.patient, doctor=self.doctor, condition="improving", notes="ok", prescription="Drink water")
        self.client.force_login(self.patient_user)
        self.assertContains(self.client.get(reverse("patient_home")), "Drink water")

    def test_patient_cannot_open_other_patient(self):
        self.client.force_login(self.patient_user)
        self.assertEqual(self.client.get(reverse("doctor_patients")).status_code, 403)
        self.assertEqual(self.client.get(reverse("patient_detail", args=[self.other_patient.id])).status_code, 403)


class StatusTests(BaseTest):
    def add(self, hr):
        Reading.objects.create(patient=self.patient, heart_rate=hr, systolic=120, diastolic=80, temperature="36.6", oxygen=98)

    def test_improving(self):
        for hr in [120, 120, 120, 70, 70, 70]:  # oldest first, newest last
            self.add(hr)
        self.assertEqual(self.patient.status(), "improving")

    def test_worsening(self):
        for hr in [70, 70, 70, 120, 120, 120]:
            self.add(hr)
        self.assertEqual(self.patient.status(), "worsening")

    def test_not_enough_data(self):
        self.add(70)
        self.assertEqual(self.patient.status(), "not enough data")


class DoctorAndDepartmentTests(BaseTest):
    def test_doctor_writes_report(self):
        self.client.force_login(self.doctor)
        self.client.post(reverse("write_report", args=[self.patient.id]),
                         {"condition": "stable", "notes": "Fine", "prescription": "Rest"})
        self.assertEqual(self.patient.reports.count(), 1)

    def test_order_goes_to_correct_department_and_is_completed(self):
        self.client.force_login(self.doctor)
        self.client.post(reverse("create_order", args=[self.patient.id]), {"service": "blood_test", "notes": ""})
        order = Order.objects.get()
        self.assertEqual(order.department, "laboratory")

        self.client.force_login(self.lab)
        self.assertContains(self.client.get(reverse("department_orders")), "Josh Marvel")
        self.client.post(reverse("start_order", args=[order.id]))
        self.client.post(reverse("complete_order", args=[order.id]), {
            "result": "All values normal", "file": SimpleUploadedFile("result.pdf", b"%PDF-1.4 result")})
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")
        self.assertEqual(order.documents.count(), 1)

    def test_other_department_cannot_change_order(self):
        order = Order.objects.create(patient=self.patient, doctor=self.doctor, service="blood_test")
        self.client.force_login(self.radiology)
        self.assertEqual(self.client.post(reverse("start_order", args=[order.id])).status_code, 403)


class EmergencyTests(BaseTest):
    def test_quick_add_patient(self):
        self.client.force_login(self.medic)
        self.client.post(reverse("emergency"), {"full_name": "Unknown", "complaint": "Accident", "priority": "critical"})
        patient = Patient.objects.get(full_name="Unknown")
        self.assertTrue(patient.is_emergency)
        self.assertContains(self.client.get(reverse("emergency")), "Accident")


class DocumentTests(BaseTest):
    def test_encrypt_and_decrypt(self):
        nonce, data = encryption.encrypt(b"secret medical file")
        self.assertNotIn(b"secret", data)
        self.assertEqual(encryption.decrypt(nonce, data), b"secret medical file")

    def test_tampered_file_is_detected(self):
        nonce, data = encryption.encrypt(b"secret medical file")
        broken = bytes([data[0] ^ 1]) + data[1:]
        with self.assertRaises(InvalidTag):
            encryption.decrypt(nonce, broken)

    def test_upload_and_download(self):
        self.client.force_login(self.patient_user)
        self.client.post(reverse("upload_document", args=[self.patient.id]),
                         {"title": "Insurance", "file": SimpleUploadedFile("card.pdf", b"%PDF my card")})
        document = Document.objects.get()
        self.assertNotIn(b"my card", bytes(document.encrypted_data))
        response = self.client.get(reverse("download_document", args=[document.id]))
        self.assertEqual(response.content, b"%PDF my card")

    def test_other_patient_cannot_download(self):
        nonce, data = encryption.encrypt(b"x")
        document = Document.objects.create(patient=self.patient, uploaded_by=self.doctor, title="t",
                                           filename="t.pdf", content_type="application/pdf", nonce=nonce, encrypted_data=data)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(reverse("download_document", args=[document.id])).status_code, 403)

    def test_wrong_file_type_rejected(self):
        self.client.force_login(self.patient_user)
        self.client.post(reverse("upload_document", args=[self.patient.id]),
                         {"title": "virus", "file": SimpleUploadedFile("virus.exe", b"MZ")})
        self.assertEqual(Document.objects.count(), 0)


class HealthTest(TestCase):
    def test_health_page(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})

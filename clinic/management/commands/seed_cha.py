import math
import os
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from clinic.models import Department, Device, DoctorProfile, Document, Message, Order, Patient, Reading, Report, ServiceType

CATALOG = {
    ("Radiology & Imaging", "imaging", "imaging", "Level 3 · West wing"): [
        ("CT scan — head", "ct-head", 45), ("CT scan — chest/abdomen", "ct-chest", 60),
        ("PET-CT scan", "pet-ct", 120), ("MRI — brain", "mri-brain", 90), ("X-ray — chest", "xr-chest", 30),
        ("Ultrasound — abdomen", "us-abd", 45),
    ],
    ("Laboratory", "lab", "lab", "Level 1 · Core lab"): [
        ("Complete blood count", "cbc", 30), ("Metabolic panel", "bmp", 45), ("Troponin", "trop", 30),
        ("Blood culture", "bcx", 240), ("Brainworm Rot type A PCR", "bwr-pcr", 90),
    ],
    ("Cardiology", "cardio", "cardio", "Level 2 · Heart centre"): [
        ("12-lead ECG", "ecg", 10), ("Echocardiogram", "echo", 60), ("Holter monitor 24h", "holter", 1440),
    ],
    ("Pharmacy", "rx", "pharmacy", "Level 1"): [
        ("Medication reconciliation", "med-rec", 60), ("Brainworm vaccine dose", "bwr-vax", 20),
    ],
}

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj "
    b"4 0 obj<</Length 74>>stream\nBT /F1 14 Tf 30 120 Td (CHA Laboratory - CBC within normal limits) Tj ET\nendstream endobj "
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
)


class Command(BaseCommand):
    help = "Creates the department/service catalogue; with --demo also creates demo users and data."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true")

    @transaction.atomic
    def handle(self, *args, demo=False, **opts):
        for (name, code, kind, loc), services in CATALOG.items():
            dept, _ = Department.objects.update_or_create(code=code, defaults={"name": name, "kind": kind, "location": loc})
            for sname, scode, minutes in services:
                ServiceType.objects.update_or_create(code=scode, defaults={"department": dept, "name": sname, "target_minutes": minutes})
        self.stdout.write(self.style.SUCCESS(f"Catalogue: {Department.objects.count()} departments, {ServiceType.objects.count()} services"))
        if demo:
            self._demo()

    def _user(self, username, role, first, last, password, **extra):
        user, created = User.objects.get_or_create(username=username, defaults={
            "role": role, "first_name": first, "last_name": last, "email": f"{username}@cha.coruscant", **extra})
        if created:
            user.set_password(password)
            user.is_approved = True
            user.save()
        return user, created

    def _demo(self):
        if Patient.objects.filter(mrn="CHA-0335227").exists():
            self.stdout.write("Demo data already present.")
            return
        rnd = random.Random(22)
        pw = os.environ.get("DEMO_PASSWORD", "Coruscant-22BBY")
        now = timezone.now()
        admin, _ = self._user("onuta", User.Role.ADMIN, "Harribore", "Onuta", pw, is_staff=True, is_superuser=True)
        carter, _ = self._user("dr.carter", User.Role.DOCTOR, "John", "Carter", pw)
        DoctorProfile.objects.get_or_create(user=carter, defaults={"specialty": "Emergency medicine", "license_number": "CRS-MD-4471"})
        venn, _ = self._user("dr.venn", User.Role.DOCTOR, "Lyra", "Venn", pw)
        DoctorProfile.objects.get_or_create(user=venn, defaults={"specialty": "Cardiology", "license_number": "CRS-MD-1189"})
        imaging = Department.objects.get(code="imaging")
        lab = Department.objects.get(code="lab")
        self._user("ct.tech", User.Role.DEPARTMENT, "Mira", "Solus", pw, department=imaging)
        self._user("lab.tech", User.Role.DEPARTMENT, "Dax", "Orrin", pw, department=lab)
        medic, _ = self._user("medic.eastport", User.Role.EMERGENCY, "Kel", "Tarrow", pw)
        # a pending registration so the approval queue is not empty
        pend, created = User.objects.get_or_create(username="dr.newhire", defaults={
            "role": User.Role.DOCTOR, "first_name": "Ana", "last_name": "Kessel", "email": "dr.newhire@cha.coruscant"})
        if created:
            pend.set_password(pw)
            pend.save()
            DoctorProfile.objects.create(user=pend, specialty="Infectious disease", license_number="CRS-MD-9902")

        # --- monitored outpatients with device data
        pu, _ = self._user("josh.marvel", User.Role.PATIENT, "Josh", "Marvel", pw)
        josh = Patient.objects.create(user=pu, mrn="CHA-0335227", first_name="Josh", last_name="Marvel",
                                      date_of_birth="1967-08-01", sex="M", blood_type="A+", allergies="Codeine",
                                      district="manarai", primary_doctor=venn, phone="+0 555 0142")
        dev = Device(patient=josh, label="VitalBand S2", kind="wearable", serial="VB-20931")
        dev.issue_token()
        dev.save()
        self._series(josh, dev, now, rnd, improving=True)

        p2u, _ = self._user("sela.dray", User.Role.PATIENT, "Sela", "Dray", pw)
        sela = Patient.objects.create(user=p2u, first_name="Sela", last_name="Dray", date_of_birth="1990-03-14", sex="F",
                                      district="coco_town", primary_doctor=venn, allergies="")
        dev2 = Device(patient=sela, label="CardioPatch", kind="patch", serial="CP-7731")
        dev2.issue_token()
        dev2.save()
        self._series(sela, dev2, now, rnd, improving=False)

        Report.objects.create(patient=josh, doctor=venn, title="Week 2 review — recovering well", condition="improving",
                              assessment="Fever has resolved since day 9. SpO₂ back above 95% at rest and heart rate trending down to 70s. NEWS2 fell from 5 to 1.",
                              suggestions="Continue amoxicillin 500 mg three times daily until the course ends (3 more days).\nKeep the VitalBand on overnight.\nGentle walks only — target 4,000 steps/day this week.\nAvoid Manarai Heights transit hubs until the Brainworm PCR is back.",
                              follow_up_on=(now + timezone.timedelta(days=7)).date())
        Message.objects.create(patient=josh, sender=pu, body="Feeling much better. Is it fine to go back to work at the Senate offices next week?")
        Message.objects.create(patient=josh, sender=venn, body="Glad to hear it. If your readings stay in the green through Friday, yes — I'll confirm after the PCR result.")

        cbc = Order.objects.create(patient=josh, service=ServiceType.objects.get(code="cbc"), ordered_by=venn, priority="routine", indication="Follow-up after febrile illness")
        cbc.advance(None)
        cbc.advance(None)
        cbc.record_result(None, "WBC 7.2, Hb 14.1, Plt 250 — within normal limits.", "normal")
        cbc.created_at = now - timezone.timedelta(days=2)
        cbc.save()
        Document.seal(data=MINIMAL_PDF, patient=josh, uploaded_by=venn, order=cbc, category="lab",
                      title="CBC result", original_name="cbc_result.pdf", content_type="application/pdf")
        Order.objects.create(patient=josh, service=ServiceType.objects.get(code="bwr-pcr"), ordered_by=venn, priority="urgent", indication="Exposure: Manarai Heights, febrile illness")
        Order.objects.create(patient=sela, service=ServiceType.objects.get(code="echo"), ordered_by=venn, priority="routine", indication="Palpitations, rising resting HR")

        # --- emergency department census
        ed = [
            ("Cunningham", "Rhea", 34, "F", 3, "Laceration, forearm", "MC3", 70),
            ("McMillion", "Bram", 61, "M", 2, "Shortness of breath", "A1", 98),
            ("Martinez", "Oso", 47, "M", 3, "Abdominal pain", "A4", 40),
            ("Tal", "Iri", 22, "F", 4, "Fever, Eastport arrival", "", 41),
            ("", "", 70, "M", 1, "Unresponsive, found Level 1313", "A7", 5),
            ("Venar", "Pell", 8, "M", 5, "Ear pain", "", 25),
            ("Quill", "Ados", 39, "X", 3, "Headache, photophobia", "", 12),
        ]
        ct = ServiceType.objects.get(code="ct-head")
        for last, first, age, sex, esi, cc, bay, mins in ed:
            p = Patient.objects.create(first_name=first, last_name=last, approx_age=age, sex=sex, acuity=esi,
                                       chief_complaint=cc, bay=bay, ed_status="in_bay" if bay else "waiting",
                                       arrived_at=now - timezone.timedelta(minutes=mins), source="emergency",
                                       is_unidentified=not last, created_by=medic, arrival_mode="ambulance" if esi <= 2 else "walk_in",
                                       primary_doctor=carter if bay else None, brainworm_screened=esi > 2)
            hr = {1: 128, 2: 112, 3: 94, 4: 88, 5: 80}[esi]
            Reading.objects.create(patient=p, source="manual", heart_rate=hr, spo2={1: 86, 2: 91}.get(esi, 97),
                                   systolic={1: 88}.get(esi, 128), resp_rate={1: 26, 2: 23}.get(esi, 16),
                                   temperature_c=Decimal("38.6") if "Fever" in cc else Decimal("37.0"),
                                   recorded_at=now - timezone.timedelta(minutes=max(mins - 3, 1)))
            if esi <= 2:
                Order.objects.create(patient=p, service=ct if esi == 1 else ServiceType.objects.get(code="xr-chest"),
                                     ordered_by=carter, priority="stat", indication=cc)
        Patient.objects.create(first_name="", last_name="", approx_age=44, sex="M", acuity=2, chief_complaint="DFD 44 · speeder collision",
                               ed_status="inbound", source="emergency", is_unidentified=True, created_by=medic, arrival_mode="ambulance")
        self.stdout.write(self.style.SUCCESS(f"Demo data created. Password for all demo users: {pw}"))

    def _series(self, patient, device, now, rnd, improving):
        """14 days of readings every 6h; one patient recovers from a fever, the other slowly deteriorates."""
        rows = []
        n = 14 * 4
        for i in range(n):
            t = now - timezone.timedelta(hours=6 * (n - i))
            x = i / n
            sick = (1 - x) ** 1.6 if improving else x ** 1.4
            circ = math.sin(i / 4 * 2 * math.pi)
            rows.append(Reading(
                patient=patient, device=device, source="device", recorded_at=t,
                heart_rate=int(68 + 40 * sick + 4 * circ + rnd.randint(-3, 3)),
                spo2=max(85, min(100, int(98 - 7 * sick + rnd.randint(-1, 1)))),
                temperature_c=Decimal(str(round(36.7 + 2.0 * sick + rnd.uniform(-0.2, 0.2), 1))),
                systolic=int(122 - 14 * sick + rnd.randint(-5, 5)),
                diastolic=int(78 - 6 * sick + rnd.randint(-4, 4)),
                resp_rate=int(14 + 9 * sick + rnd.randint(-1, 1)),
                glucose=Decimal(str(round(5.4 + rnd.uniform(-0.6, 0.9), 1))),
                steps=int(max(0, (7000 - 6000 * sick) / 4 + rnd.randint(-300, 300))),
            ))
        Reading.objects.bulk_create(rows)
        device.last_seen_at = rows[-1].recorded_at
        device.save(update_fields=["last_seen_at"])

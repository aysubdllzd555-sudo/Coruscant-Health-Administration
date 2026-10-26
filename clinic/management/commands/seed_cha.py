"""Creates demo users and data:  python manage.py seed_cha --demo"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from clinic.models import Message, Order, Patient, Reading, Report

PASSWORD = "Coruscant-22BBY"


class Command(BaseCommand):
    help = "Creates demo accounts (password Coruscant-22BBY)"

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true")

    def make_user(self, username, role, first, last, **extra):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"role": role, "first_name": first, "last_name": last, "is_approved": True, **extra},
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        return user

    def handle(self, *args, **options):
        if not options["demo"] or User.objects.filter(username="admin").exists():
            self.stdout.write("Nothing to do.")
            return

        self.make_user("admin", User.ADMIN, "Harribore", "Onuta", is_staff=True, is_superuser=True)
        doctor = self.make_user("doctor", User.DOCTOR, "Lyra", "Venn", specialty="Cardiology", license_number="CR-1189")
        self.make_user("radiology", User.DEPARTMENT, "Mira", "Solus", department="radiology")
        self.make_user("lab", User.DEPARTMENT, "Dax", "Orrin", department="laboratory")
        self.make_user("emergency", User.EMERGENCY, "Kel", "Tarrow")
        # one registration waiting for approval
        waiting = User.objects.create(username="newdoctor", role=User.DOCTOR, first_name="Ana", last_name="Kessel",
                                      license_number="CR-9902", is_approved=False)
        waiting.set_password(PASSWORD)
        waiting.save()

        patient_user = self.make_user("patient", User.PATIENT, "Josh", "Marvel")
        patient = Patient.objects.create(user=patient_user, full_name="Josh Marvel", date_of_birth="1967-08-01",
                                         gender="male", blood_type="A+", allergies="Codeine", doctor=doctor)

        # 7 days of device readings, getting better over time
        now = timezone.now()
        for i in range(14):
            sick = (14 - i) / 14
            Reading.objects.create(
                patient=patient,
                recorded_at=now - timedelta(hours=12 * (14 - i)),
                heart_rate=int(72 + 35 * sick + random.randint(-3, 3)),
                systolic=int(118 + 25 * sick), diastolic=int(76 + 10 * sick),
                temperature=Decimal(str(round(36.7 + 1.8 * sick, 1))),
                oxygen=int(98 - 6 * sick),
            )

        Report.objects.create(patient=patient, doctor=doctor, condition="improving",
                              notes="Fever is gone and oxygen is back to normal.",
                              prescription="Finish the antibiotics (3 more days). Drink plenty of water. Light walks only.")
        Order.objects.create(patient=patient, doctor=doctor, service="blood_test", notes="Check infection markers")
        Order.objects.create(patient=patient, doctor=doctor, service="ct_scan", notes="Chest CT")
        Message.objects.create(patient=patient, sender=patient_user, text="Can I go back to work next week?")
        Message.objects.create(patient=patient, sender=doctor, text="Yes, if your readings stay normal until Friday.")

        Patient.objects.create(full_name="Unknown male", is_emergency=True, complaint="Speeder accident, unconscious",
                               priority="critical", gender="male")
        Patient.objects.create(full_name="Iri Tal", is_emergency=True, complaint="High fever after travel",
                               priority="medium", gender="female")
        self.stdout.write(self.style.SUCCESS(f"Demo data created. Password for all users: {PASSWORD}"))

from django.core.management.base import BaseCommand

from clinic.crypto import load_keyring
from clinic.models import Document


class Command(BaseCommand):
    help = "Re-wraps every document key with the active (first) master key in DOCUMENT_MASTER_KEYS."

    def handle(self, *args, **opts):
        active = next(iter(load_keyring()))
        stale = Document.objects.exclude(key_id=active)
        n = 0
        for doc in stale.iterator():
            doc.rewrap()
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Re-wrapped {n} document keys under '{active}'."))

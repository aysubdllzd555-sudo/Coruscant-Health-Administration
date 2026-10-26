"""Parsing & validation of device data (API JSON payloads and CSV/JSON exports)."""
import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Reading

FIELDS = {
    # field: (type, min, max)
    "heart_rate": (int, 20, 260),
    "spo2": (int, 50, 100),
    "temperature_c": (Decimal, Decimal("30"), Decimal("45")),
    "systolic": (int, 50, 260),
    "diastolic": (int, 20, 160),
    "resp_rate": (int, 4, 70),
    "glucose": (Decimal, Decimal("1"), Decimal("40")),
    "steps": (int, 0, 200000),
}
ALIASES = {"hr": "heart_rate", "pulse": "heart_rate", "temp": "temperature_c", "temperature": "temperature_c",
           "rr": "resp_rate", "sbp": "systolic", "dbp": "diastolic", "timestamp": "recorded_at", "time": "recorded_at"}
MAX_ROWS = 5000


class IngestError(ValueError):
    pass


def _parse_time(value):
    if value in (None, ""):
        return timezone.now()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    dt = parse_datetime(str(value).strip())
    if dt is None:
        raise IngestError(f"Unrecognised timestamp '{value}' (use ISO 8601)")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    if dt > timezone.now() + timezone.timedelta(minutes=5):
        raise IngestError(f"Timestamp {value} is in the future")
    return dt


def normalise(row: dict, line: int) -> dict:
    clean = {}
    for raw_key, value in row.items():
        if raw_key is None:
            continue
        key = ALIASES.get(raw_key.strip().lower(), raw_key.strip().lower())
        if key == "recorded_at":
            clean["recorded_at"] = _parse_time(value)
            continue
        if key not in FIELDS or value in (None, ""):
            continue
        cast, lo, hi = FIELDS[key]
        try:
            v = cast(str(value).strip()) if cast is Decimal else int(float(value))
        except (ValueError, InvalidOperation):
            raise IngestError(f"Row {line}: '{raw_key}' must be a number") from None
        if not lo <= v <= hi:
            raise IngestError(f"Row {line}: {key}={v} is outside the physiological range {lo}–{hi}")
        clean[key] = v
    if not any(k in clean for k in FIELDS):
        raise IngestError(f"Row {line}: no measurements found")
    clean.setdefault("recorded_at", timezone.now())
    return clean


def parse_rows(rows):
    rows = list(rows)
    if len(rows) > MAX_ROWS:
        raise IngestError(f"Too many rows ({len(rows)}); the limit is {MAX_ROWS} per upload")
    return [normalise(r, i) for i, r in enumerate(rows, start=1)]


def parse_file(name: str, data: bytes):
    text = data.decode("utf-8-sig", errors="strict")
    if name.lower().endswith(".json"):
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("readings", [payload])
        return parse_rows(payload)
    return parse_rows(csv.DictReader(io.StringIO(text)))


def store(patient, rows, *, device=None, source=Reading.Source.DEVICE):
    objs = [Reading(patient=patient, device=device, source=source, **r) for r in rows]
    Reading.objects.bulk_create(objs)
    if device:
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])
    return objs

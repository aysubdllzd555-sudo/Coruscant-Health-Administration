# Coruscant Health Administration — Medical Management System

Django project for the Coruscant Health Administration (CHA).

## Stakeholders

| Role | What they can do |
|---|---|
| Patient | Registers (needs admin approval), uploads device data (CSV) or adds readings, sees readings, doctor's suggestions, test results, documents, messages |
| Doctor | Registers with a license number (needs approval), sees patient readings and condition (improving / stable / worsening), writes reports with prescriptions, orders services (CT, PET, MRI, X-ray, blood test, ECG) |
| Department | Receives orders for its department, starts them, uploads results (text + file) |
| Emergency services | Adds a new patient quickly (name, complaint, priority) |
| Administrator | Approves registrations, sees statistics and users, Django admin for the database |

## Technologies

- Python 3.13, Django 5.2
- PostgreSQL (Render) / SQLite (local)
- Documents encrypted with **AES-256-GCM** (`clinic/encryption.py`)
- Unit tests in `tests/test_app.py`
- CI/CD with GitHub Actions (`.github/workflows/ci.yml`): lint → tests → deploy to Render
- Hosting: Render (`render.yaml`)

## Run locally

```bash
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_cha --demo
python manage.py runserver
```

Demo users (password `Coruscant-22BBY`): `admin`, `doctor`, `patient`, `radiology`, `lab`, `emergency`.

## Tests

```bash
python manage.py test
```

## Device CSV format

```
recorded_at,heart_rate,systolic,diastolic,temperature,oxygen
2026-10-26T08:00:00,72,120,80,36.6,98
```

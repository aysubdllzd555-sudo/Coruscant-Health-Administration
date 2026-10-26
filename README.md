# Coruscant Health Administration — Medical Management System

Rebuild of the CHA Medical Management System for the medcenters of Coruscant.
Python 3.13 · Django 5.2 · PostgreSQL (SQLite locally) · AES-256-GCM encrypted documents · GitHub Actions CI/CD · Render (or any container cloud).

## Stakeholders and what each can do

| Role | Workspace | Capabilities |
|---|---|---|
| **Patient** | `/me/` | Self-register (pending admin acknowledgement) · pair wearable devices (per-device API token) · upload CSV/JSON device exports or manual readings · see vitals, charts and NEWS2 score · read doctor's reports & prescriptions · upload/download encrypted documents · message the care team |
| **Doctor** | `/worklist/` | Self-register with licence (pending approval) · worklist sorted by NEWS2 early-warning score with improving / stable / worsening trend · full chart with interactive vitals charts · write signed reports (shared with patient) · order services (CT, PET-CT, MRI, labs, ECG…) with STAT/urgent/routine priority · documents · messaging |
| **Department** | `/department/` | Kanban queue of orders for their department (STAT first, overdue highlighted) · accept → start → upload result (summary + flag + encrypted file) |
| **Emergency services** | `/ed/` | Tracking board of all bays (Acute, Minor care, Observation) with acuity colours, live timers, waiting room & inbound units · **rapid intake**: only chief complaint + ESI acuity required, unknown patients get a temporary MRN, press `N` from anywhere |
| **Administrator** | `/accounts/console/` | Approval queue for registrations · user directory · system monitor (DB latency, pending migrations, version, audit trail) · Django database admin |

## Security

* **Documents**: envelope encryption. Each file gets a random 256-bit key and is sealed with AES-256-GCM (authenticated, NIST SP 800-38D); the document UUID is bound as associated data. Data keys are wrapped by a master key from `DOCUMENT_MASTER_KEYS`; several keys allow zero-downtime rotation (`python manage.py rotate_document_keys`). Only ciphertext is stored. Uploads are type- and magic-byte checked; downloads are `no-store`, sandboxed and audited.
* Passwords hashed with scrypt; minimum 10 chars with Django validators. Accounts need admin approval.
* Role-based access on every view; patients only see their own record; departments only see orders for their department.
* Strict Content-Security-Policy (no inline scripts/styles), HSTS, secure cookies, `X-Frame-Options: DENY`.
* Device tokens are stored only as SHA-256 hashes and can be revoked.
* Append-only audit trail (chart views, downloads, orders, approvals…).

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py seed_cha --demo      # catalogue + demo users (password Coruscant-22BBY)
python manage.py runserver
```

Demo users: `onuta` (admin), `dr.venn`, `dr.carter`, `josh.marvel` (patient), `ct.tech`, `lab.tech`, `medic.eastport`.

## Tests

```bash
python manage.py test          # 33 tests: scoring, crypto, permissions, every workflow
ruff check .
```

## Device API

```http
POST /api/v1/readings
Authorization: Bearer <device token>
Content-Type: application/json

{"readings": [{"recorded_at": "2026-10-26T08:00:00Z", "heart_rate": 72, "spo2": 98, "temperature_c": 36.8}]}
```

Returns `201 {"accepted": 1, "patient": "CHA-…", "latest_news2": 0}`. Values outside physiological ranges are rejected with `400`.

## Deploy (CI/CD)

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. `render.yaml` creates the PostgreSQL database and the web service.
3. Set `DOCUMENT_MASTER_KEYS` to `k1:<key>` where key = `python -c "from clinic.crypto import generate_master_key as g; print(g())"`.
4. Copy the service's **Deploy Hook** URL into the GitHub secret `RENDER_DEPLOY_HOOK_URL`.

Every push to `main` then runs lint, migration check and tests against PostgreSQL; only if they pass is the deploy hook called, after which the workflow waits for `/healthz` to report healthy. `build.sh` applies migrations on every release, so schema upgrades ship with the code.

The `Dockerfile` runs the same app on Cloud Run, Azure Container Apps, ECS or Fly.io.

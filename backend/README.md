# Sangi Hospital Management System — Backend API

Production-grade REST API powering the Sangi Hospital HMS. Built with **Django 4.x**, **Django REST Framework**, **PostgreSQL**, and **JWT authentication**. Supports two hospital branches (Laxmi Nagar & Raya), full patient lifecycle management, role-based access control across 14 roles, cashless/cash billing flows, PDF generation, and a task assignment system for office and billing staff.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Architecture Overview](#architecture-overview)
4. [Data Model](#data-model)
5. [Role Hierarchy](#role-hierarchy)
6. [API Reference](#api-reference)
7. [Quick Start](#quick-start)
8. [Environment Variables](#environment-variables)
9. [Database & Migrations](#database--migrations)
10. [Seeding](#seeding)
11. [Available Scripts](#available-scripts)
12. [Security](#security)
13. [PDF Generation](#pdf-generation)
14. [Deployment](#deployment)
15. [Known Issues & Production Checklist](#known-issues--production-checklist)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11+ |
| Web Framework | Django 4.x + Django REST Framework |
| Database | PostgreSQL (via psycopg2) |
| Auth | JWT (SimpleJWT) — 12h access / 7d refresh |
| PDF Generation | xhtml2pdf (pisa) + Django templates |
| Excel Import | openpyxl |
| Logging | Python `logging` module (per-app loggers) |
| Media Storage | Django `MEDIA_ROOT` (local disk, swap for S3 in production) |

---

## Project Structure

```
backend/
├── sangi_hospital/
│   ├── settings.py          # All config — reads from .env
│   ├── urls.py              # Root URL router
│   ├── wsgi.py
│   └── asgi.py
├── core/
│   └── utils.py             # Shared helpers: branch resolution, task assignment,
│                            # UHID generation, billing utils, prefetch constants
├── users/
│   ├── models.py            # CustomUser with 14 roles, emp_id auto-generation
│   ├── views.py             # Login, user CRUD, OTP password reset
│   ├── serializers.py
│   ├── permissions.py       # IsBranchAdminOrSuperAdmin
│   └── urls.py
├── master/
│   ├── models.py            # ServiceMaster, MedicineMaster, Doctor, HospitalSettings
│   ├── views.py             # Rate lists, doctors, hospital settings, medicine import
│   ├── serializers.py
│   └── urls.py
├── patients/
│   ├── models.py            # Patient, Admission, MedicalHistory, Discharge,
│   │                        # Service, Billing
│   ├── views.py             # Full patient lifecycle: register, admit, discharge,
│   │                        # billing, print approval
│   ├── serializers.py       # Nested: PatientSerializer → AdmissionSerializer
│   │                        # → MedicalHistory, Discharge, Services, Billing
│   └── urls.py
├── reports/
│   ├── models.py            # LabReport, ReportMaster, DischargeSummary, PharmacyRecord
│   ├── views.py             # Lab reports, discharge summaries, pharmacy, PDF endpoints
│   ├── report_templates.py  # 43 hardcoded lab report templates (test rows, ref ranges)
│   ├── templates.py         # DISCHARGE_TEMPLATES per status (NORMAL/LAMA/DOPR/REFER/DEATH)
│   ├── serializers.py
│   ├── urls.py
│   └── templates/pdf/       # HTML templates for PDF rendering
│       ├── header.html
│       ├── admission_note.html
│       ├── medical_history.html
│       ├── normal.html      # Discharge summary — NORMAL
│       ├── lama.html
│       ├── refer.html
│       ├── dopr.html
│       ├── death.html
│       ├── bill.html
│       └── lab_reports.html
├── tasks/
│   ├── models.py            # Task, HODReview, DepartmentLogEntry
│   ├── views.py             # Task CRUD, bulk assign, analytics, HOD reviews
│   ├── serializers.py
│   └── urls.py
├── seed_superadmin.py       # One-time superadmin seed script
├── import_data.py           # Bulk patient data import utility
└── import_master_data.py    # Service master import from Excel
```

---

## Architecture Overview

- **Layered**: `urls → views → serializers → models`. Business logic lives in `views.py` and `core/utils.py`.
- **Single source of truth**: All patient data is nested under `Patient → Admission`. Every dashboard calls `GET /api/patients/` and gets the complete picture — medical history, services, billing, discharge, lab reports, pharmacy — in one response via prefetch-optimised querysets (reduces from 450+ queries to ~9).
- **Branch-scoped everything**: Branch resolution happens at the queryset level. Receptionists, branch admins, and their patients are all scoped to `branch_location`. Office side (office_admin, HOD, billing) is branch-agnostic — they see cashless patients from all branches.
- **Atomic operations**: Patient creation (UHID + first admission), new admission (ipdNo), and service bulk-save all run inside `transaction.atomic()` with `select_for_update()` to prevent race conditions.
- **Role-aware serialization**: `AdmissionSerializer.to_representation()` strips financial fields (`svcRate`, `svcTot`, `discount`, `advance`, `paidNow`) for cashless patients when the requesting user is a branch admin.

---

## Data Model

| Model | App | Key Fields | Notes |
|---|---|---|---|
| `CustomUser` | users | `role`, `branch`, `emp_id` | 14 roles, emp_id auto-generated with role-based prefix |
| `HospitalSettings` | master | `branch`, `uhid_prefix`, `slug`, logo, contact | One row per branch. Drives UHID prefix and PDF headers |
| `ServiceMaster` | master | `category`, `pricing_type`, `description`, `code`, `rate` | CASH/CASHLESS pricing. Imported from Excel |
| `MedicineMaster` | master | `name`, `batch_no`, `expiry_date`, `rate`, `quantity` | Imported from Excel with preview/confirm flow |
| `Doctor` | master | `name`, `qualification`, `branch` | Branch-scoped. Null branch = visible in all branches |
| `ReportMaster` | reports | `name` | Admin-configured report names. Drives lab suggestions |
| `Patient` | patients | `uhid`, `branch_location`, `payMode`, `cashlessType`, TPA fields | UHID unique per branch. payMode is registration snapshot |
| `Admission` | patients | `patient`, `admNo`, `ipdNo`, `payMode`, `dateTime` | admNo scoped per patient. ipdNo global. payMode drives bill_type |
| `MedicalHistory` | patients | `bp`, `pulse`, `pr`, `spo2`, vitals, complaints, diagnosis | OneToOne with Admission. pulse/pr kept in sync on save |
| `Discharge` | patients | `dischargeStatus`, `dod`, `wardName`, `roomNo`, `bedNo` | OneToOne with Admission. Status drives PDF template |
| `Service` | patients | `svcName`, `svcCode`, `svcCat`, `svcRate`, `svcQty`, `svcTot` | FK to Admission. Bulk-replaced on each save |
| `Billing` | patients | `bill_type`, `discount`, `advance`, `paidNow`, `printStatus` | OneToOne with Admission. printStatus: DRAFT→PENDING→APPROVED |
| `LabReport` | reports | `report_name`, `report_type`, `tests` (JSONField), `amount` | FK to Admission |
| `PharmacyRecord` | reports | `medicine_name`, `batch_no`, `quantity`, `rate`, `amount` | FK to Admission |
| `DischargeSummary` | reports | `summary_type`, `content` (JSONField) | OneToOne with Admission. Auto-prefilled from MedicalHistory |
| `Task` | tasks | `assigned_by`, `assigned_to`, `patient`, `admission`, `status` | Per-admission tracking. SET_NULL on admission delete |
| `HODReview` | tasks | `employee`, `rating`, `performance_score`, `period` | HOD performance reviews |
| `DepartmentLogEntry` | tasks | `department`, `branch`, `record_date`, `data` (JSONField) | Daily department logs |

---

## Role Hierarchy

```
Super Admin
├── Creates: Branch Admin, Office Admin, all roles
├── Sees: All patients, all branches, all data
└── Approves: Print requests for cash patients

Branch Admin (per branch)
├── Creates: Receptionists (own branch only)
├── Sees: All patients in own branch (cash + cashless)
├── Cashless patients: financial amounts hidden
└── Approves: Print requests for cash patients (own branch)

Office Admin
├── Creates: HOD, Billing, OPD, Intimation, Query, Uploading,
│           Nursing, Notes, Medical Officer, Quality Analyst
├── Sees: All cashless patients (both branches)
└── Assigns: Tasks to any central staff role

    HOD
    ├── Sees: All cashless patients (both branches)
    ├── Assigns: Tasks to staff
    └── Reviews: Employee performance

        Billing / OPD / Intimation / Query / Uploading /
        Nursing / Notes / Medical Officer / Quality Analyst
        └── Sees: Only patients assigned to them via tasks

Receptionist (per branch)
└── Registers patients, fills all clinical data, requests prints
```

---

## API Reference

**Base URL:** `http://localhost:8000/api`

All routes except `GET /hospital-settings/` and `POST /users/login/` require:
```
Authorization: Bearer <access_token>
```

---

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| POST | `/users/login/` | — | Login. Returns `access` + `refresh` JWT tokens with `role`, `branch`, `emp_id` |
| GET | `/users/me/` | ✓ | Get own profile |
| POST | `/users/token/refresh/` | — | Refresh access token |
| POST | `/users/request-reset-otp/` | — | Send OTP to email for password reset |
| POST | `/users/verify-reset-otp/` | — | Verify OTP and set new password |

---

### Hospital Settings

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/hospital-settings/` | — | Public | All branches (used for login branch dropdown) |
| GET | `/hospital-settings/{id}/` | — | Public | Single branch |
| POST | `/hospital-settings/` | ✓ | Superadmin | Create new branch |
| PATCH | `/hospital-settings/{id}/` | ✓ | Superadmin | Update branch settings (logo, address, etc.) |
| DELETE | `/hospital-settings/{id}/` | ✓ | Superadmin | Delete branch (blocked if has patients or users) |

---

### Master Data

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/service-master/` | ✓ | All | Full rate list. Filter: `?pricing_type=CASHLESS&category=ROOM CHARGE` |
| GET | `/medicine-master/` | ✓ | All | Full medicine list. Filter: `?search=paracetamol` |
| POST | `/medicine-master/` | ✓ | Superadmin, Office Admin | Create single medicine |
| POST | `/medicine-master/preview/` | ✓ | Superadmin, Office Admin | Preview Excel import (no DB write) |
| POST | `/medicine-master/import/` | ✓ | Superadmin, Office Admin | Confirm Excel import (replaces all) |
| GET | `/doctors/` | ✓ | Branch-scoped | Doctors for this branch + global doctors |
| POST | `/doctors/` | ✓ | Superadmin, Branch Admin | Add doctor (branch admin auto-scoped to their branch) |
| PATCH | `/doctors/{id}/` | ✓ | Superadmin, Branch Admin | Update doctor |
| DELETE | `/doctors/{id}/` | ✓ | Superadmin, Branch Admin | Delete doctor |
| GET | `/report-master/` | ✓ | All | Admin-configured lab report names |
| POST | `/report-master/` | ✓ | Admin+ | Add report name to master list |
| GET | `/admin-stats/` | ✓ | Superadmin, Admin, Office Admin | Today's discharge count (branch-scoped for admin) |

---

### User Management

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/users/next-emp-id/` | ✓ | Admin+ | Preview next emp_id before creation |
| GET | `/users/manage/` | ✓ | Admin+ | List users (scoped by role — see hierarchy) |
| POST | `/users/manage/` | ✓ | Admin+ | Create user. Role restrictions enforced |
| GET | `/users/manage/{id}/` | ✓ | Admin+ | Single user profile |
| PATCH | `/users/manage/{id}/` | ✓ | Admin+ | Update user details |
| DELETE | `/users/manage/{id}/` | ✓ | Admin+ | Deactivate/delete user |
| PATCH | `/users/manage/{id}/reset-password/` | ✓ | Admin+ | Force-reset user password |

---

### Patients

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/patients/` | ✓ | Role-scoped | Patient list. Branch admin → own branch. Office admin → cashless only. Billing → via tasks only |
| POST | `/patients/` | ✓ | Receptionist, Admin | Register patient + create admission 1 atomically |
| GET | `/patients/{uhid}/` | ✓ | Role-scoped | Full patient profile with all admissions nested |
| PATCH | `/patients/{uhid}/` | ✓ | Receptionist, Admin | Update patient demographics |
| POST | `/patients/{uhid}/new_admission/` | ✓ | Receptionist, Admin | Create new admission (admNo increments, ipdNo generated) |
| PATCH | `/patients/{uhid}/update_medical/` | ✓ | Receptionist, Billing, Admin | Save/update medical history for an admission |
| PATCH | `/patients/{uhid}/discharge/` | ✓ | Receptionist, Admin | Save/update discharge details |
| PATCH | `/patients/{uhid}/update_billing/` | ✓ | Receptionist, Billing, Admin | Save/update billing (discount, advance, paymentMode) |
| PATCH | `/patients/{uhid}/set_expected_dod/` | ✓ | Receptionist, Admin | Set expected date of discharge |
| POST | `/patients/{uhid}/admissions/{adm_no}/services/bulk-save/` | ✓ | Receptionist, Billing | Replace all services for an admission |
| POST | `/patients/{uhid}/request_print/` | ✓ | Receptionist | Request print approval (cash patients only) |
| POST | `/patients/{uhid}/resolve_print/` | ✓ | Superadmin, Branch Admin | Approve or reject print request |
| GET | `/patients/pending_prints/` | ✓ | Superadmin, Branch Admin | All patients with pending print requests (cash only) |

---

### Lab Reports

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/patients/{uhid}/admissions/{adm_no}/lab-report-templates/` | ✓ | All | Report suggestions: receptionist-saved reports first, then ReportMaster formats |
| GET | `/patients/{uhid}/admissions/{adm_no}/lab-reports/` | ✓ | All | Saved lab reports for this admission |
| POST | `/patients/{uhid}/admissions/{adm_no}/lab-reports/bulk-save/` | ✓ | Billing, Admin | Save/replace lab reports |
| GET | `/patients/{uhid}/admissions/{adm_no}/lab-reports/print/` | ✓ | All | Generate lab reports PDF |

---

### Pharmacy Records

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/patients/{uhid}/admissions/{adm_no}/pharmacy-records/` | ✓ | All | Pharmacy records for this admission |
| POST | `/patients/{uhid}/admissions/{adm_no}/pharmacy-records/bulk-save/` | ✓ | Billing, Admin | Save pharmacy records |
| PATCH | `/patients/{uhid}/admissions/{adm_no}/pharmacy-records/{id}/` | ✓ | Billing, Admin | Update single record |
| DELETE | `/patients/{uhid}/admissions/{adm_no}/pharmacy-records/{id}/` | ✓ | Billing, Admin | Delete single record |
| GET | `/patients/{uhid}/admissions/{adm_no}/pharmacy-records/print/` | ✓ | All | Generate pharmacy PDF |

---

### Discharge Summary

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/patients/{uhid}/admissions/{adm_no}/dynamic-summary/` | ✓ | All | Load summary. Returns saved content if exists; otherwise builds template pre-filled from MedicalHistory + Discharge. Query: `?type=NORMAL\|LAMA\|DOPR\|REFER\|DEATH` |
| POST | `/patients/{uhid}/admissions/{adm_no}/dynamic-summary/` | ✓ | Billing, Admin | Save summary content |
| GET | `/patients/{uhid}/admissions/{adm_no}/dynamic-summary/print/` | ✓ | All | Generate discharge summary PDF (uses DB data even without saved summary) |

---

### PDF Documents

| Method | Endpoint | Auth | Description |
|---|---|:---:|---|
| GET | `/patients/{uhid}/admissions/{adm_no}/admission-note/print/` | ✓ | Admission note PDF |
| GET | `/patients/{uhid}/admissions/{adm_no}/medical-history/print/` | ✓ | Medical history PDF |
| GET | `/patients/{uhid}/admissions/{adm_no}/bill/print/` | ✓ | Final bill PDF with all services, totals, discount |
| GET | `/patients/{uhid}/admissions/{adm_no}/canonical-records/` | ✓ | Consolidated view of all admission records |

---

### Task Management

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/tasks/` | ✓ | Role-scoped | Task list. Office Admin/Superadmin → all. HOD → assigned by/to. Staff → assigned to them |
| POST | `/tasks/` | ✓ | Office Admin, HOD, Superadmin | Create task (single patient) |
| GET | `/tasks/{id}/` | ✓ | Role-scoped | Single task with full patient detail |
| PATCH | `/tasks/{id}/` | ✓ | Office Admin, HOD | Update task (priority, description) |
| DELETE | `/tasks/{id}/` | ✓ | Office Admin, HOD | Delete task |
| POST | `/tasks/bulk-assign/` | ✓ | Office Admin, HOD, Superadmin | Assign multiple patients to one employee |
| GET | `/tasks/eligible-employees/` | ✓ | Office Admin, HOD | Employees for a department with task counts |
| GET | `/tasks/analytics/` | ✓ | Office Admin, HOD | Per-employee breakdown: total, completed, pending, overdue |
| GET | `/tasks/report/` | ✓ | Office Admin, HOD | Full report with patient details per task |
| PATCH | `/tasks/{id}/update-status/` | ✓ | Staff | Mark task complete (locks after completion) |
| GET | `/tasks/my-tasks/` | ✓ | Staff | Only tasks assigned to the logged-in employee |

---

### HOD Dashboard

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| GET | `/hod/employees/` | ✓ | HOD | Employees in a department. Filter: `?department=Billing` |
| POST | `/hod/tasks/` | ✓ | HOD | Assign single patient task |
| GET | `/hod/tasks/` | ✓ | HOD | All tasks. Filter: `?employeeId=1&status=Pending&date=2026-05-07` |
| PATCH | `/hod/tasks/{id}/` | ✓ | HOD | Update task |
| DELETE | `/hod/tasks/{id}/` | ✓ | HOD | Delete task |
| GET | `/hod/analytics/` | ✓ | HOD | Stats + per-employee breakdown with completion rates |
| POST | `/hod/reviews/` | ✓ | HOD | Submit performance review |
| GET | `/hod/reviews/` | ✓ | HOD | Reviews for a department. Filter: `?department=Billing` |
| GET | `/hod/reports/download/` | ✓ | HOD | Download department report as CSV |
| GET | `/hod/performance-ratings/` | ✓ | HOD | All HOD reviews across departments |

---

### Department Logs

| Method | Endpoint | Auth | Who | Description |
|---|---|:---:|---|---|
| POST | `/department-logs/bulk-save/` | ✓ | OPD/Intimation/Query/Uploading/Nursing etc. | Submit daily log entries |
| GET | `/department-logs/` | ✓ | Staff, HOD, Admin | Fetch logs. Filter: `?department=OPD&branch=LNM` |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- pip + virtualenv

### Install & Run

```bash
# 1. Clone and navigate
cd backend

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your values (see next section)

# 5. Run migrations
python manage.py migrate

# 6. Seed the superadmin
python seed_superadmin.py

# 7. (Optional) Import service master from Excel
python import_master_data.py

# 8. Start the server
python manage.py runserver
```

API available at `http://localhost:8000/api/`

---

## Environment Variables

All sensitive values must be in `.env`. The server reads them via `os.getenv()`.

| Variable | Required | Default | Notes |
|---|:---:|---|---|
| `SECRET_KEY` | ✓ | — | Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | — | `False` | Set `True` in development only |
| `ALLOWED_HOSTS` | ✓ (prod) | `localhost,127.0.0.1` | Comma-separated. Add your domain in production |
| `DB_NAME` | ✓ | — | PostgreSQL database name |
| `DB_USER` | ✓ | — | PostgreSQL user |
| `DB_PASSWORD` | ✓ | — | PostgreSQL password |
| `DB_HOST` | — | `localhost` | |
| `DB_PORT` | — | `5432` | |
| `EMAIL_HOST` | — | — | SMTP host for OTP emails |
| `EMAIL_PORT` | — | `587` | |
| `EMAIL_HOST_USER` | — | — | SMTP username |
| `EMAIL_HOST_PASSWORD` | — | — | SMTP password |
| `CORS_ALLOWED_ORIGINS` | ✓ (prod) | — | Frontend origin(s), comma-separated |

### `.env.example`

```env
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

DB_NAME=sangi_hospital
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

CORS_ALLOWED_ORIGINS=http://localhost:5173,https://yourfrontend.com
```

---

## Database & Migrations

```bash
# Apply all pending migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations

# Production — apply without prompts
python manage.py migrate --no-input
```

### Migration order matters

The `patients` app depends on `tasks` (for the admission FK). Always run `migrate` as a whole — never per-app in isolation.

---

## Seeding

### Superadmin

```bash
python seed_superadmin.py
```

Creates a superadmin user. Edit the script to set username/password before first run. Safe to re-run (uses `get_or_create`).

### Service Master (from Excel)

```bash
python import_master_data.py
```

Imports the SANGIESIC rate list. Requires the Excel file path configured inside the script.

### Medicine Master (via API)

```
POST /api/medicine-master/preview/    ← validate first
POST /api/medicine-master/import/     ← confirm with { "confirmed": "true" }
```

---

## Available Scripts

| Command | Description |
|---|---|
| `python manage.py runserver` | Start development server |
| `python manage.py migrate` | Apply all migrations |
| `python manage.py makemigrations` | Create new migrations |
| `python manage.py createsuperuser` | Django admin superuser (separate from HMS superadmin) |
| `python seed_superadmin.py` | Seed HMS superadmin account |
| `python import_master_data.py` | Import service master from Excel |
| `python manage.py collectstatic` | Collect static files for production |

---

## Security

- **JWT** — HS256, 12-hour access token, 7-day refresh. Tokens include `role`, `branch`, `emp_id` in payload.
- **SECRET_KEY** — Read from `.env`. Falls back to an insecure default in development — never use the default in production.
- **Role enforcement** — Every viewset checks `request.user.role` before returning data or allowing writes. Enforced at queryset level (not just permission classes).
- **Branch isolation** — Branch admin and receptionist queries are always filtered by `branch_location = user.branch`. Cross-branch access is impossible at the ORM level.
- **Atomic UHID/ipdNo generation** — `select_for_update()` inside `transaction.atomic()` prevents duplicate IDs under concurrent requests.
- **Financial data hiding** — `AdmissionSerializer` strips all financial fields for cashless patients when the requestor is a branch admin. Done in `to_representation()` — cannot be bypassed by query params.
- **Print approval** — Cash patients only. Cashless patients are blocked at both `request_print` and `resolve_print` endpoints.
- **Password reset** — OTP-based, 10-minute expiry, single-use.

> ⚠️ **Critical:** All PDF print endpoints currently have `permission_classes = []`. Anyone with the URL can access patient PDFs without logging in. Change to `permission_classes = [IsAuthenticated]` before going to production.

---

## PDF Generation

All PDFs are generated server-side using `xhtml2pdf` (pisa) rendering Django HTML templates.

| PDF | Endpoint | Template |
|---|---|---|
| Admission Note | `/admission-note/print/` | `pdf/admission_note.html` |
| Medical History | `/medical-history/print/` | `pdf/medical_history.html` |
| Discharge Summary (Normal) | `/dynamic-summary/print/` | `pdf/normal.html` |
| Discharge Summary (LAMA) | `/dynamic-summary/print/` | `pdf/lama.html` |
| Discharge Summary (DOPR) | `/dynamic-summary/print/` | `pdf/dopr.html` |
| Discharge Summary (Refer) | `/dynamic-summary/print/` | `pdf/refer.html` |
| Discharge Summary (Death) | `/dynamic-summary/print/` | `pdf/death.html` |
| Final Bill | `/bill/print/` | `pdf/bill.html` |
| Lab Reports | `/lab-reports/print/` | `pdf/lab_reports.html` |
| Pharmacy Records | `/pharmacy-records/print/` | `pdf/pharmacy_records.html` |

Hospital logo, address, phone, email, and website auto-populate on every PDF from `HospitalSettings` for the patient's branch.

---

## Deployment

```bash
# 1. Set all environment variables (especially SECRET_KEY, DB_*, ALLOWED_HOSTS)
# 2. Install dependencies
pip install -r requirements.txt

# 3. Collect static files
python manage.py collectstatic --no-input

# 4. Run migrations
python manage.py migrate --no-input

# 5. Seed superadmin (first deploy only)
python seed_superadmin.py

# 6. Start with Gunicorn
gunicorn sangi_hospital.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

Front with Nginx for TLS termination and static file serving. Point `MEDIA_ROOT` to a persistent volume or swap for S3/Cloudinary for patient documents.

---

*Maintained by the Sangi Hospital engineering team.*
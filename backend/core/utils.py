import datetime
from decimal import Decimal, InvalidOperation
from django.db import models
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination

class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

# ── Constants ──────────────────────────────────────────────────────────────────

TASK_MANAGER_ROLES = {'superadmin', 'office_admin', 'admin', 'hod'}
TASK_ASSIGNABLE_ROLES = {
    'receptionist', 'billing', 'hod', 'opd', 'intimation', 'query', 'uploading',
    'nursing', 'notes', 'medical_officer', 'quality_analyst',
}

DEPARTMENT_ROLE_MAP = {
    'HOD': 'hod',
    'Billing': 'billing',
    'Uploading': 'uploading',
    'Query': 'query',
    'OPD': 'opd',
    'Intimation': 'intimation',
    'Receptionist': 'receptionist',
    'Nursing': 'nursing',
    'Doctor': 'doctor',
    'Notes': 'notes',
    'Quality Analysis': 'quality_analyst',
}

DEPARTMENT_LOG_FIELDS = {
    'opd': ['uploadDate', 'createdAt', 'opdDate'],
    'intimation': ['uploadDate', 'createdAt', 'doa'],
    'query': ['queryRepDate', 'createdAt', 'raiseDate'],
    'uploading': ['uploadDate', 'createdAt', 'doa'],
}

# ── Branch helpers (inline imports prevent circular dependency) ────────────────

def get_default_branch_code():
    from master.models import HospitalSettings
    default_branch = HospitalSettings.objects.order_by('id').first()
    return default_branch.branch if default_branch else 'LNM'


def get_branch_settings(branch_code):
    from master.models import HospitalSettings
    if not branch_code:
        branch_code = get_default_branch_code()
    settings_obj = HospitalSettings.objects.filter(branch=str(branch_code).upper()).first()
    if settings_obj:
        return settings_obj
    return HospitalSettings(
        branch=str(branch_code).upper(),
        slug=str(branch_code).lower(),
        branch_name=str(branch_code).upper(),
        hospital_name="SANGI HOSPITAL",
        uhid_prefix=str(branch_code).upper()[:3] or "SH",
    )


def get_branch_settings_queryset():
    from master.models import HospitalSettings
    return HospitalSettings.objects.all().order_by('branch_name', 'branch')


def get_valid_branch_codes():
    return set(get_branch_settings_queryset().values_list('branch', flat=True))


def resolve_branch_code_from_loc(loc_id=None, explicit_branch=None):
    from master.models import HospitalSettings
    if explicit_branch:
        branch = str(explicit_branch).strip().upper()
        if HospitalSettings.objects.filter(branch=branch).exists():
            return branch
    if loc_id:
        slug = str(loc_id).strip().lower()
        branch_obj = HospitalSettings.objects.filter(slug=slug).first()
        if branch_obj:
            return branch_obj.branch
    default_branch = HospitalSettings.objects.order_by('id').first()
    return default_branch.branch if default_branch else 'LNM'

# ── Billing helper ─────────────────────────────────────────────────────────────

def get_or_create_current_billing(admission):
    from patients.models import Billing
    billing = admission.bills.order_by('-id').first()
    if billing:
        return billing, False
    pay_mode = str(getattr(admission.patient, 'payMode', '') or '').lower()
    initial_bill_type = 'CASHLESS' if 'cashless' in pay_mode else 'CASH'
    return Billing.objects.create(admission=admission, bill_type=initial_bill_type), True

# ── Service pricing helpers ────────────────────────────────────────────────────

def normalize_service_pricing(service_data, patient=None):
    raw_pricing = str(
        service_data.get('pricing_type')
        or service_data.get('pricingApplied')
        or service_data.get('pricing_applied')
        or ''
    ).strip().upper()
    if raw_pricing in {'CASH', 'CASHLESS'}:
        return raw_pricing
    pay_mode = str(getattr(patient, 'payMode', '') or '').lower()
    return 'CASHLESS' if 'cashless' in pay_mode else 'CASH'


def resolve_service_defaults(service_data, patient=None):
    from master.models import ServiceMaster
    svc_name = (
        service_data.get('svcName') or
        service_data.get('title') or
        service_data.get('name') or ''
    ).strip()
    if not svc_name:
        raise ValueError('Service name (svcName) is required.')

    pricing_applied = normalize_service_pricing(service_data, patient)
    svc_date = service_data.get('svcDate') or service_data.get('date') or None

    try:
        svc_qty = int(service_data.get('svcQty') or service_data.get('qty') or 1)
    except (TypeError, ValueError):
        svc_qty = 1
    svc_qty = max(1, svc_qty)

    master_service = ServiceMaster.objects.filter(
        description__iexact=svc_name,
        pricing_type=pricing_applied,
    ).first()

    if master_service:
        svc_rate = master_service.rate
        svc_cat = master_service.category
        svc_code = master_service.code
    else:
        raw_rate = service_data.get('svcRate') or service_data.get('rate') or 0
        raw_cat = service_data.get('svcCat') or service_data.get('type') or 'GENERAL SERVICES'
        svc_code = service_data.get('svcCode') or service_data.get('code') or ''
        try:
            svc_rate = Decimal(str(raw_rate))
        except (InvalidOperation, ValueError, TypeError):
            svc_rate = Decimal('0')
        svc_cat = raw_cat

    return {
        'svcName': svc_name,
        'svcCode': svc_code,
        'pricing_applied': pricing_applied,
        'svcCat': svc_cat,
        'svcQty': svc_qty,
        'svcRate': svc_rate,
        'svcTot': svc_rate * svc_qty,
        'svcDate': svc_date,
    }

# ── Task helpers ───────────────────────────────────────────────────────────────

def normalize_task_status(raw_status, due_date=None):
    status_map = {
        'pending': 'Pending',
        'in-progress': 'In Progress',
        'completed': 'Completed',
        'on-hold': 'On Hold',
        'overdue': 'Overdue',
    }
    safe_status = status_map.get(str(raw_status or '').strip().lower(), 'Pending')
    if safe_status != 'Completed' and due_date and due_date < timezone.now():
        return 'Overdue'
    return safe_status


def serialize_task_for_hod(task):
    patient = task.patient
    status_value = task.status
    if status_value != 'Completed' and task.due_date and task.due_date < timezone.now():
        status_value = 'Overdue'

    status_map = {
        'Pending': 'pending',
        'In Progress': 'in-progress',
        'Completed': 'completed',
        'On Hold': 'pending',
        'Overdue': 'overdue',
    }
    priority_map = {
        'Low': 'low',
        'Medium': 'medium',
        'High': 'high',
        'Urgent': 'high',
    }

    employee_name = task.assigned_to.get_full_name().strip() or task.assigned_to.username

    patient_type = 'TPA'
    if patient:
        if (patient.cashlessType or '').lower().find('card') >= 0:
            patient_type = 'Card'
        elif (patient.payMode or '').lower().find('cash') >= 0:
            patient_type = 'Cash'

    return {
        'id': task.id,
        'employeeId': task.assigned_to_id,
        'employeeName': employee_name,
        'taskType': task.title,
        'patientId': patient.uhid if patient else '',
        'patientType': patient_type,
        'priority': priority_map.get(task.priority, 'medium'),
        'dueDate': task.due_date.date().isoformat() if task.due_date else '',
        'status': status_map.get(status_value, 'pending'),
        'notes': task.description or '',
        'department': task.department,
    }


def get_task_queryset_for_user(user):
    from tasks.models import Task
    queryset = (
        Task.objects
        .select_related('assigned_to', 'assigned_by', 'patient')
        .prefetch_related(
            'patient__admissions',
            'patient__admissions__medicalHistory',
            'patient__admissions__discharge',
            'patient__admissions__services',
            'patient__admissions__bills',
            'patient__admissions__lab_reports',
            'patient__admissions__pharmacy_records',
        )
        .order_by('-created_at')
    )
    if user.role in ['superadmin', 'office_admin']:
        return queryset
    if user.role == 'admin':
        return queryset.filter(
            models.Q(assigned_to__branch=user.branch) |
            models.Q(assigned_by=user)
        )
    if user.role == 'hod':
        return queryset.filter(models.Q(assigned_to=user) | models.Q(assigned_by=user))
    return queryset.filter(assigned_to=user)


def validate_generic_task_assignment(actor, assigned_to, patient=None, department=None):
    valid_branch_codes = get_valid_branch_codes()
    if actor.role not in TASK_MANAGER_ROLES:
        raise PermissionDenied("You are not allowed to manage tasks from this dashboard.")

    if actor.role == 'superadmin':
        allowed_roles = TASK_ASSIGNABLE_ROLES | {'admin', 'office_admin'}
    else:
        allowed_roles = TASK_ASSIGNABLE_ROLES

    if assigned_to.role not in allowed_roles:
        raise PermissionDenied(
            f"{actor.get_role_display()} cannot assign tasks to {assigned_to.get_role_display()} accounts."
        )

    if (
        patient and
        actor.role not in {'office_admin', 'superadmin', 'hod'} and
        assigned_to.branch in valid_branch_codes and
        patient.branch_location != assigned_to.branch
    ):
        raise ValidationError({'patient': 'Selected patient must belong to the same branch as the assigned employee.'})

    expected_role = get_department_role(department)
    if expected_role and assigned_to.role != expected_role:
        raise ValidationError({
            'assigned_to': f"Department '{department}' tasks must be assigned to a '{expected_role}' user."
        })

    if expected_role == 'billing' and patient is None:
        raise ValidationError({'patient': 'Billing tasks must be linked to a patient.'})

    if actor.role == 'admin' and assigned_to.branch != actor.branch:
        raise PermissionDenied("Branch Admin can assign tasks only inside their own branch.")

    if (
        patient and
        actor.role not in {'office_admin', 'superadmin'} and
        assigned_to.branch in valid_branch_codes and
        patient.branch_location != assigned_to.branch
    ):
        raise ValidationError({'patient': 'Selected patient must belong to the same branch as the assigned employee.'})


def get_department_role(department):
    return DEPARTMENT_ROLE_MAP.get(str(department or '').strip(), '')


def get_allowed_hod_departments(user):
    if user.role in ('superadmin', 'office_admin', 'hod'):
        return list(DEPARTMENT_ROLE_MAP.keys())
    return []


def ensure_hod_access(request):
    role = getattr(request.user, 'role', '')
    if not request.user.is_authenticated or role not in ['hod', 'office_admin', 'superadmin']:
        return Response({'error': 'Unauthorized access.'}, status=status.HTTP_403_FORBIDDEN)
    return None


def coerce_record_date(department, payload):
    for key in DEPARTMENT_LOG_FIELDS.get(department, []):
        value = payload.get(key)
        if not value:
            continue
        if isinstance(value, str):
            safe_value = value[:10]
            try:
                return datetime.date.fromisoformat(safe_value)
            except ValueError:
                continue
    return timezone.localdate()
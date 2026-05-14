import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction, models
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.utils import (
    StandardPagination,
    get_or_create_current_billing,
    resolve_service_defaults,
    resolve_branch_code_from_loc,
    get_valid_branch_codes,
    DEPARTMENT_ROLE_MAP,          # Single source of truth — defined in core/utils
)
from .models import Patient, Admission, MedicalHistory, Discharge, Service, Billing
from .serializers import (
    PatientSerializer,
    ServiceSerializer,
    AdmissionSerializer,
)

logger = logging.getLogger(__name__)

# ── The standard prefetch used on every patient queryset ──────────────────────
# This eliminates the N+1 problem. Without this, a list of 50 patients fires
# 450+ DB queries. With it: exactly 9 queries total regardless of list size.
_PATIENT_PREFETCH = [
    'admissions',
    'admissions__medicalHistory',
    'admissions__discharge',
    'admissions__services',
    'admissions__billing',
    'admissions__lab_reports',
    'admissions__pharmacy_records',
]


def _clean_pay_mode(raw):
    """Normalise payMode to 'cash' or 'cashless'. Always defaults to 'cash'."""
    return 'cashless' if str(raw or '').strip().lower() == 'cashless' else 'cash'


def _safe_adm_no(raw):
    """
    Parse admNo to int. Returns None for empty input.
    Raises ValidationError (400) for non-numeric values.
    """
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValidationError({'admNo': f'Invalid admNo: {raw!r}. Must be an integer.'})


def _get_admission_strict(patient, adm_no):
    """
    Fetch admission that MUST belong to this patient.
    Never uses get_or_create — prevents ghost admissions.
    """
    return get_object_or_404(Admission, patient=patient, admNo=adm_no)


# ── PatientViewSet ─────────────────────────────────────────────────────────────

class PatientViewSet(viewsets.ModelViewSet):
    pagination_class = StandardPagination
    queryset         = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    lookup_field        = 'uhid'
    lookup_value_regex  = '[^/]+'

    def _base_queryset(self):
        """Base queryset with all prefetches applied."""
        return Patient.objects.prefetch_related(*_PATIENT_PREFETCH)

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'is_authenticated', False):
            return Patient.objects.none()

        qs = self._base_queryset()

        # Assignment-modal exclusion (frontend sends this to hide already-assigned patients)
        exclude_dept = self.request.query_params.get('exclude_active_tasks_for_dept')
        if exclude_dept:
            qs = qs.exclude(
                assigned_tasks__department__iexact=exclude_dept,
                assigned_tasks__status__in=['Pending', 'In Progress'],
            )

        role = user.role

        if role == 'superadmin':
            # Sees everything, all branches
            return qs.order_by('-created_at')

        elif role == 'office_admin':
            # Sees ONLY patients who have at least one cashless admission.
            # Patient.payMode is the registration snapshot — not filtered here.
            cashless_adm = Admission.objects.filter(patient=OuterRef('pk'), payMode='cashless')
            return qs.filter(Exists(cashless_adm)).order_by('-created_at')

        elif role in ('admin', 'receptionist'):
            # Branch-scoped: all patients (cash + cashless) for their branch only
            return qs.filter(branch_location=user.branch).order_by('-created_at')

        elif role == 'hod':
            # All cashless patients (both branches) + patients on their task board
            cashless_adm = Admission.objects.filter(patient=OuterRef('pk'), payMode='cashless')
            return qs.filter(
                models.Q(assigned_tasks__assigned_to=user) |
                models.Q(assigned_tasks__assigned_by=user) |
                models.Q(Exists(cashless_adm))
            ).distinct().order_by('-created_at')

        elif role in (
            'billing', 'opd', 'intimation', 'query', 'uploading',
            'nursing', 'notes', 'medical_officer', 'quality_analyst',
        ):
            # Staff: only patients explicitly assigned to them via tasks
            return qs.filter(assigned_tasks__assigned_to=user).distinct().order_by('-created_at')

        return Patient.objects.none()

    # ── Create patient (atomic) ────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        admission_type = data.pop('admissionType', None) or 'IPD'
        adm_pay_mode   = _clean_pay_mode(data.get('payMode'))

        # Auto-fill branch from the logged-in receptionist/admin if not sent
        if not data.get('branch_location') and not data.get('locId'):
            if getattr(request.user, 'branch', None) not in (None, 'ALL'):
                data['branch_location'] = request.user.branch

        if 'locId' in data or 'branch_location' in data:
            data['branch_location'] = resolve_branch_code_from_loc(
                data.get('locId'), data.get('branch_location')
            )

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Patient + first Admission created together.
                # If admission creation fails, patient is rolled back.
                self.perform_create(serializer)
                patient = serializer.instance
                Admission.objects.create(
                    patient=patient,
                    admNo=1,
                    admissionType=admission_type,
                    payMode=adm_pay_mode,
                )
            response_serializer = self.get_serializer(patient)
            headers = self.get_success_headers(response_serializer.data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        except Exception:
            logger.exception('Patient creation failed. data=%s', dict(data))
            raise

    # ── New admission ──────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='new_admission')
    def new_admission(self, request, uhid=None):
        patient        = get_object_or_404(Patient, uhid=uhid)
        admission_type = request.data.get('admissionType') or 'IPD'
        adm_pay_mode   = _clean_pay_mode(request.data.get('payMode'))

        try:
            with transaction.atomic():
                # Lock patient row — prevents race condition on admNo generation
                patient    = Patient.objects.select_for_update().get(pk=patient.pk)
                last_adm   = Admission.objects.filter(patient=patient).order_by('-admNo').first()
                new_adm_no = (last_adm.admNo + 1) if last_adm else 1

                admission = Admission.objects.create(
                    patient=patient,
                    admNo=new_adm_no,
                    admissionType=admission_type,
                    payMode=adm_pay_mode,
                )
                # Seed billing immediately so payMode is locked in from the start
                get_or_create_current_billing(admission)

            serializer = self.get_serializer(patient)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception:
            logger.exception('New admission failed. uhid=%s', uhid)
            raise

    # ── Update medical history ─────────────────────────────────────────────────

    @action(detail=True, methods=['patch'])
    def update_medical(self, request, uhid=None):
        patient      = self.get_object()
        medical_data = request.data.get('medicalData', {})

        try:
            adm_no        = _safe_adm_no(request.data.get('admNo') or 1)
            admission_obj = _get_admission_strict(patient, adm_no)
            med_hist, _   = MedicalHistory.objects.get_or_create(admission=admission_obj)

            for key, value in medical_data.items():
                if key in ('id', 'admission'):
                    continue
                setattr(med_hist, key, value)

            med_hist.save()
            return Response({'status': 'Medical history updated successfully'})

        except ValidationError:
            raise
        except Exception:
            logger.exception('update_medical failed. uhid=%s', uhid)
            raise

    # ── Discharge ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['patch'])
    def discharge(self, request, uhid=None):
        patient        = self.get_object()
        discharge_data = request.data.get('dischargeData', {})

        try:
            adm_no        = _safe_adm_no(request.data.get('admNo') or 1)
            admission_obj = _get_admission_strict(patient, adm_no)
            discharge_obj, _ = Discharge.objects.get_or_create(admission=admission_obj)

            for key, value in discharge_data.items():
                if key in ('id', 'admission'):
                    continue
                if key in ('dod', 'expectedDod', 'actualDod') and value == '':
                    value = None
                setattr(discharge_obj, key, value)

            discharge_obj.save()
            return Response({'status': 'Discharge updated successfully'})

        except ValidationError:
            raise
        except Exception:
            logger.exception('discharge failed. uhid=%s', uhid)
            raise

    # ── Billing ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['patch'])
    def update_billing(self, request, uhid=None):
        patient      = self.get_object()
        billing_data = request.data.get('billingData', {})

        try:
            adm_no        = _safe_adm_no(request.data.get('admNo') or 1)
            admission_obj = _get_admission_strict(patient, adm_no)
            billing_obj, _ = get_or_create_current_billing(admission_obj)

            for key, value in billing_data.items():
                # Never allow staff saves to overwrite admin print approvals
                if key in ('id', 'admission', 'printStatus', 'printRequestedAt'):
                    continue
                if key in ('discount', 'advance', 'paidNow'):
                    if value in ('', None):
                        value = Decimal('0')
                    else:
                        try:
                            value = Decimal(str(value))
                        except (InvalidOperation, ValueError, TypeError):
                            value = Decimal('0')
                setattr(billing_obj, key, value)

            # bill_type anchors to Admission.payMode — never silently flips a cashless to CASH
            adm_pay_mode = str(getattr(admission_obj, 'payMode', '') or '').lower()
            if adm_pay_mode == 'cashless':
                billing_obj.bill_type = 'CASHLESS'
            else:
                pay_mode      = str(billing_data.get('paymentMode') or getattr(billing_obj, 'paymentMode', '') or '')
                insurance_type = str(billing_data.get('insuranceType') or getattr(billing_obj, 'insuranceType', '') or '')
                cashless_like = {'tpa', 'echs', 'eci', 'fci', 'ayushman bharat', 'northern railways', 'insurance'}
                billing_obj.bill_type = 'CASHLESS' if (
                    'cashless' in pay_mode.lower() or
                    insurance_type.strip().lower() in cashless_like
                ) else 'CASH'

            billing_obj.save()
            return Response({'status': 'Billing updated successfully'})

        except ValidationError:
            raise
        except Exception:
            logger.exception('update_billing failed. uhid=%s', uhid)
            raise

    # ── Add single service ─────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def add_service(self, request, uhid=None):
        patient      = self.get_object()
        service_data = request.data.get('serviceData')

        try:
            adm_no        = _safe_adm_no(request.data.get('admNo') or 1)
            admission_obj = _get_admission_strict(patient, adm_no)
            defaults      = resolve_service_defaults(service_data or {}, patient, admission=admission_obj)

            service, _ = Service.objects.update_or_create(
                admission=admission_obj,
                svcName=defaults['svcName'],
                pricing_applied=defaults['pricing_applied'],
                defaults={
                    'svcCat':  defaults['svcCat'],
                    'svcQty':  defaults['svcQty'],
                    'svcRate': defaults['svcRate'],
                    'svcTot':  defaults['svcTot'],
                    'svcDate': defaults['svcDate'],
                    'svcCode': defaults['svcCode'],
                },
            )
            return Response({
                'status': 'Service added successfully.',
                'data': ServiceSerializer(service).data,
            })

        except ValidationError:
            raise
        except Exception:
            logger.exception('add_service failed. uhid=%s', uhid)
            raise

    # ── Set expected discharge date ────────────────────────────────────────────

    @action(detail=True, methods=['patch'])
    def set_expected_dod(self, request, uhid=None):
        patient       = self.get_object()
        expected_date = request.data.get('expectedDod')

        if expected_date == '':
            expected_date = None
        elif expected_date and len(expected_date) > 10:
            expected_date = expected_date[:10]

        try:
            adm_no = _safe_adm_no(request.data.get('admNo'))
            if adm_no is None:
                return Response({'error': 'admNo is required.'}, status=status.HTTP_400_BAD_REQUEST)

            admission = _get_admission_strict(patient, adm_no)
            if not hasattr(admission, 'discharge'):
                Discharge.objects.create(admission=admission)
            admission.discharge.expectedDod = expected_date
            admission.discharge.save()
            return Response({'status': 'Expected DOD updated successfully'})

        except ValidationError:
            raise
        except Exception:
            logger.exception('set_expected_dod failed. uhid=%s', uhid)
            raise

    # ── Request print ──────────────────────────────────────────────────────────

        @action(detail=True, methods=['post'])
        def request_print(self, request, uhid=None):
            patient     = self.get_object()
            raw_adm_no  = (
                request.data.get('admNo') or request.data.get('adm_no') or
                request.query_params.get('admNo') or request.query_params.get('adm_no')
            )
    
            try:
                if raw_adm_no in (None, ''):
                    admission = patient.admissions.order_by('-admNo').first()
                    if not admission:
                        return Response({'error': 'No admission found.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    admission = _get_admission_strict(patient, _safe_adm_no(raw_adm_no))
    
                # FIX: Cashless patients do NOT go through the print approval flow.
                # Only CASH admissions need Branch Admin approval before printing.
                if admission.payMode.lower() == 'cashless':
                    return Response(
                        {'error': 'Print approval is only required for cash patients. Cashless bills are managed by the office.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
    
                billing_obj, _ = get_or_create_current_billing(admission)
                if billing_obj.printStatus == 'APPROVED':
                    return Response({'status': 'Already approved'})
    
                billing_obj.printStatus      = 'PENDING'
                billing_obj.printRequestedAt = timezone.now()
                billing_obj.save()
                return Response({'status': 'Print request sent to Branch Admin', 'admNo': admission.admNo})
    
            except ValidationError:
                raise
            except Exception:
                logger.exception('request_print failed. uhid=%s', uhid)
                raise

    # ── Resolve print (admin approval) ────────────────────────────────────────

        @action(detail=True, methods=['post'])
        def resolve_print(self, request, uhid=None):
            role = getattr(request.user, 'role', '')
            if role not in ('superadmin', 'office_admin', 'admin', 'branchadmin'):
                return Response({'error': 'Only Branch Admin / Super Admin can approve print requests.'}, status=status.HTTP_403_FORBIDDEN)
    
            patient    = self.get_object()
            raw_adm_no = (
                request.data.get('admNo') or request.data.get('adm_no') or
                request.query_params.get('admNo') or request.query_params.get('adm_no')
            )
            action_val = str(
                request.data.get('action') or request.data.get('status') or request.data.get('backendAction') or 'APPROVED'
            ).upper()
            if action_val not in {'APPROVED', 'REJECTED', 'PENDING'}:
                action_val = 'APPROVED'
    
            try:
                if role in ('admin', 'branchadmin') and getattr(request.user, 'branch', None):
                    if patient.branch_location != request.user.branch:
                        return Response({'error': 'You can only resolve print requests for your own branch.'}, status=status.HTTP_403_FORBIDDEN)
    
                if raw_adm_no in (None, ''):
                    admission = patient.admissions.order_by('-admNo').first()
                    if not admission:
                        return Response({'error': 'No admission found.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    admission = _get_admission_strict(patient, _safe_adm_no(raw_adm_no))
    
                # FIX: Block approval for cashless patients — they don't use this flow.
                if admission.payMode.lower() == 'cashless':
                    return Response(
                        {'error': 'Cashless patients do not use the print approval flow.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
    
                billing_obj, _ = get_or_create_current_billing(admission)
                billing_obj.printStatus = action_val
                billing_obj.save()
                return Response({'status': f'Print request {action_val}'})
    
            except ValidationError:
                raise
            except Exception:
                logger.exception('resolve_print failed. uhid=%s', uhid)
                raise

    # ── Pending prints list ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def pending_prints(self, request):
        role = getattr(request.user, 'role', '')
        if role not in ('superadmin', 'office_admin', 'admin', 'branchadmin'):
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
 
        # FIX 1: 'admissions__bills__printStatus' → 'admissions__billing__printStatus'
        # FIX 2: Added admissions__payMode=cash — cashless patients never appear here
        qs = Patient.objects.filter(
            admissions__billing__printStatus='PENDING',
            admissions__payMode='cash',             # CASH patients only
        ).prefetch_related(*_PATIENT_PREFETCH)
 
        if role in ('admin', 'branchadmin') and getattr(request.user, 'branch', None):
            qs = qs.filter(branch_location=request.user.branch)
 
        serializer = self.get_serializer(qs.distinct(), many=True)
        return Response(serializer.data)


# ── ServiceBulkSaveAPIView ─────────────────────────────────────────────────────

class ServiceBulkSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uhid, adm_no):
        patient  = get_object_or_404(Patient, uhid=uhid)
        services = request.data.get('services') or []

        if not isinstance(services, list):
            return Response({'error': 'services must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        adm_no_int    = _safe_adm_no(adm_no)
        admission_obj = get_object_or_404(Admission, patient=patient, admNo=adm_no_int)

        try:
            with transaction.atomic():
                # Build all new Service objects first — if any fail, old services are untouched
                new_services = [
                    Service(
                        admission=admission_obj,
                        **{k: v for k, v in resolve_service_defaults(
                            sd or {}, patient, admission=admission_obj
                        ).items()}
                    )
                    for sd in services
                ]
                # Only delete after we know the new list is fully valid
                admission_obj.services.all().delete()
                if new_services:
                    Service.objects.bulk_create(new_services)

            saved = ServiceSerializer(
                admission_obj.services.order_by('svcDate', 'id'), many=True
            ).data
            return Response({'saved': len(saved), 'services': saved}, status=status.HTTP_200_OK)

        except ValidationError:
            raise
        except Exception:
            logger.exception('ServiceBulkSave failed. uhid=%s admNo=%s', uhid, adm_no)
            raise
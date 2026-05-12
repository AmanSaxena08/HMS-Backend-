import datetime
import os
import csv
import json
import copy
import base64
import io
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from django.utils import timezone
from django.db import transaction, models
from django.db.models import Count, Q, Exists, OuterRef, Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from users import permissions
from users.models import CustomUser
from master.models import HospitalSettings, ServiceMaster
from core.utils import (
    get_default_branch_code,
    get_branch_settings,
    get_valid_branch_codes,
    get_or_create_current_billing,
    resolve_service_defaults,
    normalize_service_pricing,
    DEPARTMENT_ROLE_MAP,
    resolve_branch_code_from_loc,
)
from .models import Patient, Admission, MedicalHistory, Discharge, Service, Billing
from .serializers import (
    PatientSerializer,
    MedicalHistorySerializer,
    DischargeSerializer,
    ServiceSerializer,
    BillingSerializer,
    AdmissionSerializer,
)

logger = logging.getLogger(__name__)

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


def _clean_pay_mode(raw):
    """Normalize a raw payMode string to 'cash' or 'cashless'. Defaults to 'cash'."""
    val = str(raw or '').strip().lower()
    return 'cashless' if val == 'cashless' else 'cash'


def _safe_adm_no(raw):
    """
    Parse admNo from request data. Returns int or None.
    Raises ValidationError for non-numeric values so callers get a clean 400.
    """
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValidationError({'admNo': f'Invalid admNo value: {raw!r}. Must be an integer.'})


def _get_admission_strict(patient, adm_no):
    """
    Fetch a specific admission that MUST belong to this patient.
    Never uses get_or_create — avoids ghost admissions.
    Raises 404 if not found.
    """
    return get_object_or_404(Admission, patient=patient, admNo=adm_no)


class PatientViewSet(viewsets.ModelViewSet):
    from core.utils import StandardPagination
    pagination_class = StandardPagination
    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    lookup_field = 'uhid'
    lookup_value_regex = '[^/]+'

    def get_queryset(self):
        user = self.request.user

        if not getattr(user, 'is_authenticated', False):
            return Patient.objects.none()

        queryset = Patient.objects.all()

        # Only hides patients if the frontend explicitly asks (for the Assignment Modal)
        exclude_dept = self.request.query_params.get('exclude_active_tasks_for_dept')
        if exclude_dept:
            queryset = queryset.exclude(
                assigned_tasks__department__iexact=exclude_dept,
                assigned_tasks__status__in=['Pending', 'In Progress']
            )

        # Super Admin: Sees everything
        if user.role == 'superadmin':
            return queryset.order_by('-created_at')

        # Office Admin: Sees ONLY patients who have at least one cashless admission.
        # Patient.payMode is the initial registration snapshot — not filtered here.
        elif user.role == 'office_admin':
            cashless_admission = Admission.objects.filter(
                patient=OuterRef('pk'),
                payMode='cashless'
            )
            return queryset.filter(
                Exists(cashless_admission)
            ).order_by('-created_at')

        # Branch Admin & Receptionist: See ALL patients for THEIR branch only
        elif user.role in ['admin', 'receptionist']:
            return queryset.filter(branch_location=user.branch).order_by('-created_at')

        # HOD: Sees ALL cashless patients (all branches) + tasks assigned to/by them
        elif user.role == 'hod':
            cashless_admission = Admission.objects.filter(
                patient=OuterRef('pk'),
                payMode='cashless'
            )
            return queryset.filter(
                models.Q(assigned_tasks__assigned_to=user) |
                models.Q(assigned_tasks__assigned_by=user) |
                models.Q(Exists(cashless_admission))
            ).distinct().order_by('-created_at')

        # Staff: See ONLY patients explicitly assigned to them
        elif user.role in [
            'billing', 'opd', 'intimation', 'query', 'uploading',
            'nursing', 'notes', 'medical_officer', 'quality_analyst'
        ]:
            return queryset.filter(
                assigned_tasks__assigned_to=user
            ).distinct().order_by('-created_at')

        return queryset.none()

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        admission_type = data.pop('admissionType', None) or request.data.get('admissionType') or 'IPD'
        adm_pay_mode = _clean_pay_mode(data.get('payMode'))

        # If no branch sent, use the logged-in user's branch
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
            # Atomic: patient + first admission created together.
            # If admission creation fails, patient is rolled back too.
            with transaction.atomic():
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

        except Exception as e:
            logger.exception('Patient creation failed for data=%s', data)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='new_admission')
    def new_admission(self, request, uhid=None):
        patient = get_object_or_404(Patient, uhid=uhid)
        admission_type = request.data.get('admissionType') or 'IPD'
        adm_pay_mode = _clean_pay_mode(request.data.get('payMode'))

        try:
            with transaction.atomic():
                # Lock patient row to prevent race condition on admNo generation
                patient = Patient.objects.select_for_update().get(pk=patient.pk)

                last_adm = Admission.objects.filter(patient=patient).order_by('-admNo').first()
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

        except Exception as e:
            logger.exception('New admission failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['patch'])
    def update_medical(self, request, uhid=None):
        patient = self.get_object()
        medical_data = request.data.get('medicalData', {})

        try:
            adm_no = _safe_adm_no(request.data.get('admNo') or 1)
            # Strict fetch — never silently create ghost admissions
            admission_obj = _get_admission_strict(patient, adm_no)
            med_hist, _ = MedicalHistory.objects.get_or_create(admission=admission_obj)

            for key, value in medical_data.items():
                if key in ('id', 'admission'):
                    continue
                setattr(med_hist, key, value)

            med_hist.save()
            return Response({'status': 'Medical history updated successfully'})

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('update_medical failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def discharge(self, request, uhid=None):
        patient = self.get_object()
        discharge_data = request.data.get('dischargeData', {})

        try:
            adm_no = _safe_adm_no(request.data.get('admNo') or 1)
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
        except Exception as e:
            logger.exception('discharge failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_billing(self, request, uhid=None):
        patient = self.get_object()
        billing_data = request.data.get('billingData', {})

        try:
            adm_no = _safe_adm_no(request.data.get('admNo') or 1)
            admission_obj = _get_admission_strict(patient, adm_no)
            billing_obj, _ = get_or_create_current_billing(admission_obj)

            for key, value in billing_data.items():
                # Protect printStatus/printRequestedAt — staff saves must not overwrite admin approvals
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

            # bill_type anchors to Admission.payMode — the per-admission value set at
            # registration time. Never silently flip a cashless admission to CASH.
            adm_pay_mode = str(getattr(admission_obj, 'payMode', '') or '').lower()
            if adm_pay_mode == 'cashless':
                billing_obj.bill_type = 'CASHLESS'
            else:
                # Cash admission — also check if a specific cashless insurance was entered
                pay_mode = str(
                    billing_data.get('paymentMode') or
                    getattr(billing_obj, 'paymentMode', '') or ''
                )
                insurance_type = str(
                    billing_data.get('insuranceType') or
                    getattr(billing_obj, 'insuranceType', '') or ''
                )
                cashless_like = {
                    'tpa', 'echs', 'eci', 'fci',
                    'ayushman bharat', 'northern railways', 'insurance'
                }
                billing_obj.bill_type = 'CASHLESS' if (
                    'cashless' in pay_mode.lower() or
                    insurance_type.strip().lower() in cashless_like
                ) else 'CASH'

            billing_obj.save()
            return Response({'status': 'Billing updated successfully'})

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('update_billing failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_service(self, request, uhid=None):
        patient = self.get_object()
        service_data = request.data.get('serviceData')

        try:
            adm_no = _safe_adm_no(request.data.get('admNo') or 1)
            admission_obj = _get_admission_strict(patient, adm_no)
            # Pass admission so pricing reads Admission.payMode, not Patient.payMode
            defaults = resolve_service_defaults(service_data or {}, patient, admission=admission_obj)

            service, created = Service.objects.update_or_create(
                admission=admission_obj,
                svcName=defaults['svcName'],
                pricing_applied=defaults['pricing_applied'],
                defaults={
                    'svcCat': defaults['svcCat'],
                    'svcQty': defaults['svcQty'],
                    'svcRate': defaults['svcRate'],
                    'svcTot': defaults['svcTot'],
                    'svcDate': defaults['svcDate'],
                    'svcCode': defaults['svcCode'],
                }
            )

            return Response({
                'status': 'Service added successfully with automated pricing.',
                'data': ServiceSerializer(service).data
            })

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('add_service failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def set_expected_dod(self, request, uhid=None):
        patient = self.get_object()
        expected_date = request.data.get('expectedDod')

        if expected_date == '':
            expected_date = None
        elif expected_date and len(expected_date) > 10:
            expected_date = expected_date[:10]

        try:
            adm_no = _safe_adm_no(request.data.get('admNo'))
            if adm_no is None:
                return Response(
                    {'error': 'admNo is required for set_expected_dod.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            admission = _get_admission_strict(patient, adm_no)

            if not hasattr(admission, 'discharge'):
                Discharge.objects.create(admission=admission)

            admission.discharge.expectedDod = expected_date
            admission.discharge.save()
            return Response({'status': 'Expected DOD updated successfully'})

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('set_expected_dod failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def request_print(self, request, uhid=None):
        patient = self.get_object()
        raw_adm_no = (
            request.data.get('admNo') or
            request.data.get('adm_no') or
            request.query_params.get('admNo') or
            request.query_params.get('adm_no')
        )

        try:
            if raw_adm_no in (None, ''):
                admission = patient.admissions.order_by('-admNo').first()
                if not admission:
                    return Response(
                        {'error': 'No admission found for this patient.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                adm_no = _safe_adm_no(raw_adm_no)
                admission = _get_admission_strict(patient, adm_no)

            billing_obj, _ = get_or_create_current_billing(admission)

            # Don't reset an already-approved bill back to PENDING
            if billing_obj.printStatus == 'APPROVED':
                return Response({'status': 'Already approved'})

            billing_obj.printStatus = 'PENDING'
            billing_obj.printRequestedAt = timezone.now()
            billing_obj.save()
            return Response({
                'status': 'Print request sent to Branch Admin',
                'admNo': admission.admNo
            })

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('request_print failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def resolve_print(self, request, uhid=None):
        role = getattr(request.user, 'role', '')
        if role not in ['superadmin', 'office_admin', 'admin', 'branchadmin']:
            return Response(
                {'error': 'Only Branch Admin / Super Admin can approve print requests.'},
                status=status.HTTP_403_FORBIDDEN
            )

        patient = self.get_object()
        raw_adm_no = (
            request.data.get('admNo') or
            request.data.get('adm_no') or
            request.query_params.get('admNo') or
            request.query_params.get('adm_no')
        )

        action_val = str(
            request.data.get('action') or
            request.data.get('status') or
            request.data.get('backendAction') or
            'APPROVED'
        ).upper()
        if action_val not in {'APPROVED', 'REJECTED', 'PENDING'}:
            action_val = 'APPROVED'

        try:
            if (
                role in ('admin', 'branchadmin') and
                getattr(request.user, 'branch', None) and
                patient.branch_location != request.user.branch
            ):
                return Response(
                    {'error': 'You can only resolve print requests for your own branch.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if raw_adm_no in (None, ''):
                admission = patient.admissions.order_by('-admNo').first()
                if not admission:
                    return Response(
                        {'error': 'No admission found for this patient.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                adm_no = _safe_adm_no(raw_adm_no)
                admission = _get_admission_strict(patient, adm_no)

            billing_obj, _ = get_or_create_current_billing(admission)
            billing_obj.printStatus = action_val
            billing_obj.save()
            return Response({'status': f'Print request {action_val}'})

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('resolve_print failed for uhid=%s', uhid)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def pending_prints(self, request):
        role = getattr(request.user, 'role', '')
        if role not in ['superadmin', 'office_admin', 'admin', 'branchadmin']:
            return Response(
                {'error': 'Unauthorized access.'},
                status=status.HTTP_403_FORBIDDEN
            )

        pending_patients = Patient.objects.filter(admissions__bills__printStatus='PENDING')
        if role in ('admin', 'branchadmin') and getattr(request.user, 'branch', None):
            pending_patients = pending_patients.filter(branch_location=request.user.branch)
        pending_patients = pending_patients.distinct()

        serializer = self.get_serializer(pending_patients, many=True)
        return Response(serializer.data)

    # cashless_records endpoint — removed (dead code, replaced by get_queryset office_admin filter)


class ServiceBulkSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uhid, adm_no):
        patient = get_object_or_404(Patient, uhid=uhid)
        services = request.data.get('services') or []

        if not isinstance(services, list):
            return Response(
                {'error': 'services must be a list.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            adm_no_int = _safe_adm_no(adm_no)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Strict fetch — never create ghost admissions via get_or_create
        admission_obj = get_object_or_404(Admission, patient=patient, admNo=adm_no_int)

        try:
            serialized = []
            with transaction.atomic():
                # Build new service objects first, THEN delete old ones.
                # This means if build fails, old services are untouched.
                new_services = []
                for service_data in services:
                    defaults = resolve_service_defaults(
                        service_data or {}, patient, admission=admission_obj
                    )
                    new_services.append(Service(
                        admission=admission_obj,
                        svcName=defaults['svcName'],
                        svcCode=defaults['svcCode'],
                        pricing_applied=defaults['pricing_applied'],
                        svcCat=defaults['svcCat'],
                        svcQty=defaults['svcQty'],
                        svcRate=defaults['svcRate'],
                        svcTot=defaults['svcTot'],
                        svcDate=defaults['svcDate'],
                    ))

                # Only delete after we know the new list is valid
                admission_obj.services.all().delete()
                if new_services:
                    Service.objects.bulk_create(new_services)

                serialized = ServiceSerializer(
                    admission_obj.services.order_by('svcDate', 'id'), many=True
                ).data

            return Response({'saved': len(serialized), 'services': serialized}, status=status.HTTP_200_OK)

        except ValidationError:
            raise
        except Exception as e:
            logger.exception('ServiceBulkSave failed for uhid=%s admNo=%s', uhid, adm_no)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
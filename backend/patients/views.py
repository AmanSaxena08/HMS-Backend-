import datetime
import os
import csv
import json
import copy
import base64
import io
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

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    lookup_field = 'uhid'
    lookup_value_regex = '[^/]+'

    def get_queryset(self):
        user = self.request.user

        if not getattr(user, 'is_authenticated', False):
            return Patient.objects.none()

        queryset = Patient.objects.all()

        # 🌟 THE TASK FIX: Only hides patients if the frontend explicitly asks (for the Assignment Modal)
        exclude_dept = self.request.query_params.get('exclude_active_tasks_for_dept')
        if exclude_dept:
            queryset = queryset.exclude(
                assigned_tasks__department__iexact=exclude_dept,
                assigned_tasks__status__in=['Pending', 'In Progress']
            )

        # 1a. Super Admin: Sees everything
        if user.role == 'superadmin':
            return queryset.order_by('-created_at')

        # 1b. Office Admin: Sees ONLY cashless patients from ALL branches
        elif user.role == 'office_admin':
            from django.db.models import Exists, OuterRef
            cashless_bill = Billing.objects.filter(
                admission__patient=OuterRef('pk'),
                bill_type='CASHLESS'
            )
            return queryset.filter(
                models.Q(payMode__icontains='cashless') |
                models.Q(Exists(cashless_bill))
            ).order_by('-created_at')

        # 2. 🏥 Branch Admin & Receptionist: See ALL patients for THEIR branch
        elif user.role in ['admin', 'receptionist']:
            return queryset.filter(branch_location=user.branch).order_by('-created_at')

        # 3. 👔 HOD: Sees ALL CASHLESS patients (all hospitals) + Tasks assigned to/by them
        elif user.role == 'hod':
            from django.db.models import Exists, OuterRef
            cashless_bill = Billing.objects.filter(
                admission__patient=OuterRef('pk'),
                bill_type='CASHLESS'
            )
            return queryset.filter(
                models.Q(assigned_tasks__assigned_to=user) |
                models.Q(assigned_tasks__assigned_by=user) |
                models.Q(payMode__icontains='cashless') |
                models.Q(Exists(cashless_bill))
            ).distinct().order_by('-created_at')

        # 4. 👩‍⚕️ Staff (Created by Office Admin/HOD): See ONLY patients explicitly assigned to them
        elif user.role in ['billing', 'opd', 'intimation', 'query', 'uploading', 'nursing', 'notes', 'medical_officer', 'quality_analyst']:
            return queryset.filter(assigned_tasks__assigned_to=user).distinct().order_by('-created_at')

        return queryset.none()
    
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        admission_type = data.pop('admissionType', None) or request.data.get('admissionType') or 'IPD'

         # If no branch sent, use the logged-in user's branch (not DB first branch)
        if not data.get('branch_location') and not data.get('locId'):
            if getattr(request.user, 'branch', None) not in [None, 'ALL']:
                data['branch_location'] = request.user.branch
        
        if 'locId' in data or 'branch_location' in data:
            data['branch_location'] = resolve_branch_code_from_loc(data.get('locId'), data.get('branch_location'))
            
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        patient = serializer.instance 

        try:
            Admission.objects.create(patient=patient, admNo=1, admissionType=admission_type)
            response_serializer = self.get_serializer(patient)
            headers = self.get_success_headers(response_serializer.data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            print("🚨 AUTO-ADMISSION FAILED:", str(e))
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='new_admission')
    def new_admission(self, request, uhid=None): 
        try:
            # 🌟 THE FIX: Fetch the patient manually using the UHID from the URL
            # This guarantees it won't fail trying to find a default 'pk'
            patient = get_object_or_404(Patient, uhid=uhid)
            
            admission_type = request.data.get('admissionType') or 'IPD'
            
            last_adm = Admission.objects.filter(patient=patient).order_by('id').last()
            new_adm_no = (last_adm.admNo + 1) if last_adm else 1
            
            admission = Admission.objects.create(
                patient=patient, 
                admNo=new_adm_no,
                admissionType=admission_type,
            )
            
            # Return the fully updated patient profile to the frontend
            serializer = self.get_serializer(patient)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print("🚨 ADMISSION CREATION FAILED:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
               

    @action(detail=True, methods=['patch'])
    def update_medical(self, request, uhid=None):
        patient = self.get_object()
        adm_no = request.data.get('admNo') or 1
        medical_data = request.data.get('medicalData', {})
        
        try:
            admission_obj, _ = Admission.objects.get_or_create(patient=patient, admNo=adm_no)
            med_hist, _ = MedicalHistory.objects.get_or_create(admission=admission_obj)
                
            for key, value in medical_data.items():
                if key in ['id', 'admission']:
                    continue
                setattr(med_hist, key, value)
                
            med_hist.save()
            return Response({'status': 'Medical history updated successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def discharge(self, request, uhid=None):
        patient = self.get_object()
        adm_no = request.data.get('admNo') or 1
        discharge_data = request.data.get('dischargeData', {})
        
        try:
            admission_obj, _ = Admission.objects.get_or_create(patient=patient, admNo=adm_no)
            discharge_obj, _ = Discharge.objects.get_or_create(admission=admission_obj)
                
            for key, value in discharge_data.items():
                if key in ['id', 'admission']: 
                    continue
                if key in ['dod', 'expectedDod', 'actualDod'] and value == "":
                    value = None
                setattr(discharge_obj, key, value)
                
            discharge_obj.save()
            return Response({'status': 'Discharge updated successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['patch'])
    def update_billing(self, request, uhid=None):
        patient = self.get_object()
        adm_no = request.data.get('admNo') or 1
        billing_data = request.data.get('billingData', {})
        
        try:
            admission_obj, _ = Admission.objects.get_or_create(patient=patient, admNo=adm_no)
            billing_obj, _ = get_or_create_current_billing(admission_obj)
                
            for key, value in billing_data.items():
                # 🌟 PROTECT STATUS: Ignore printStatus so staff saves don't overwrite Admin approvals!
                if key in ['id', 'admission', 'printStatus', 'printRequestedAt']: 
                    continue
                    
                if key in ['discount', 'advance', 'paidNow']:
                    if value in ["", None]:
                        value = Decimal('0')
                    else:
                        try:
                            value = Decimal(str(value))
                        except (InvalidOperation, ValueError, TypeError):
                            value = Decimal('0')
                    
                setattr(billing_obj, key, value)

            pay_mode = str(billing_data.get('paymentMode') or getattr(billing_obj, 'paymentMode', '') or '')
            insurance_type = str(billing_data.get('insuranceType') or getattr(billing_obj, 'insuranceType', '') or '')
            cashless_like = {'tpa', 'echs', 'eci', 'fci', 'ayushman bharat', 'northern railways', 'insurance'}
            billing_obj.bill_type = 'CASHLESS' if (
                'cashless' in pay_mode.lower() or insurance_type.strip().lower() in cashless_like
            ) else 'CASH'
                
            billing_obj.save()
            return Response({'status': 'Billing updated successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_service(self, request, uhid=None):
        patient = self.get_object()
        adm_no = request.data.get('admNo') or 1
        service_data = request.data.get('serviceData')
        
        try:
            admission_obj, _ = Admission.objects.get_or_create(patient=patient, admNo=adm_no)
            defaults = resolve_service_defaults(service_data or {}, patient)
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
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def set_expected_dod(self, request, uhid=None):
        patient = self.get_object()
        adm_no = request.data.get('admNo')
        expected_date = request.data.get('expectedDod')
        
        if expected_date == "":
            expected_date = None
        elif expected_date and len(expected_date) > 10:
            expected_date = expected_date[:10]

        try:
            admission = patient.admissions.get(admNo=adm_no)
            if not hasattr(admission, 'discharge'):
                Discharge.objects.create(admission=admission)
            
            admission.discharge.expectedDod = expected_date
            admission.discharge.save()
            return Response({'status': 'Expected DOD updated successfully'})
        except Exception as e:
            print("🚨 DOD ERROR:", str(e))
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def request_print(self, request, uhid=None):
        patient = self.get_object()
        adm_no = (
            request.data.get('admNo')
            or request.data.get('adm_no')
            or request.query_params.get('admNo')
            or request.query_params.get('adm_no')
        )
        
        try:
            if adm_no in [None, ""]:
                admission = patient.admissions.order_by('-admNo').first()
                if not admission:
                    return Response({'error': 'No admission found for this patient.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                admission = patient.admissions.get(admNo=int(adm_no))
            billing_obj, _ = get_or_create_current_billing(admission)
            
            # 🌟 SMART CHECK: Prevent resetting an already approved bill back to PENDING!
            if billing_obj.printStatus == 'APPROVED':
                return Response({'status': 'Already approved'})

            billing_obj.printStatus = 'PENDING'
            billing_obj.printRequestedAt = timezone.now()
            billing_obj.save()
            return Response({'status': 'Print request sent to Branch Admin', 'admNo': admission.admNo})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def resolve_print(self, request, uhid=None):
        role = getattr(request.user, 'role', '')
        if role not in ['superadmin', 'office_admin', 'admin', 'branchadmin']:
            return Response({'error': 'Only Branch Admin / Super Admin can approve print requests.'}, status=status.HTTP_403_FORBIDDEN)

        patient = self.get_object()
        adm_no = (
            request.data.get('admNo')
            or request.data.get('adm_no')
            or request.query_params.get('admNo')
            or request.query_params.get('adm_no')
        )
        
        action = request.data.get('action') or request.data.get('status') or request.data.get('backendAction') or 'APPROVED'
        action = str(action).upper()
        if action not in {'APPROVED', 'REJECTED', 'PENDING'}:
            action = 'APPROVED'
        
        try:
            if role in ['admin', 'branchadmin'] and getattr(request.user, 'branch', None) and patient.branch_location != request.user.branch:
                return Response({'error': 'You can only resolve print requests for your own branch.'}, status=status.HTTP_403_FORBIDDEN)
            if adm_no in [None, ""]:
                admission = patient.admissions.order_by('-admNo').first()
                if not admission:
                    return Response({'error': 'No admission found for this patient.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                admission = patient.admissions.get(admNo=int(adm_no))
            billing_obj, _ = get_or_create_current_billing(admission)
            billing_obj.printStatus = action
            billing_obj.save()
                
            return Response({'status': f'Print request {action}'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def pending_prints(self, request):
        role = getattr(request.user, 'role', '')
        if role not in ['superadmin', 'office_admin', 'admin', 'branchadmin']:
            return Response({'error': 'Unauthorized access.'}, status=status.HTTP_403_FORBIDDEN)

        pending_patients = Patient.objects.filter(admissions__bills__printStatus='PENDING')
        if role in ['admin', 'branchadmin'] and getattr(request.user, 'branch', None):
            pending_patients = pending_patients.filter(branch_location=request.user.branch)
        pending_patients = pending_patients.distinct()
        
        serializer = self.get_serializer(pending_patients, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='cashless-records')
    def cashless_records(self, request):
        # 1. Strict Security Check: Only Office Admins can hit this endpoint
        if getattr(request.user, 'role', '') != 'office_admin':
            return Response(
                {"error": "Unauthorized access. Only Office Admins can view the corporate dashboard."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 2. Database Query: Find patients linked to an admission that has a cashless bill
        # The .distinct() ensures we don't get duplicate patients if they have multiple cashless visits
        from .models import Patient
        cashless_patients = Patient.objects.filter(admissions__bills__bill_type='CASHLESS').distinct()
        
        # 3. Serialize and Return
        # Because the user is 'office_admin', our updated serializer will naturally 
        # expose all the prices and totals we hid from the hospital staff!
        serializer = self.get_serializer(cashless_patients, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ServiceBulkSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uhid, adm_no):
        patient = get_object_or_404(Patient, uhid=uhid)
        admission_obj, _ = Admission.objects.get_or_create(patient=patient, admNo=adm_no)
        services = request.data.get('services') or []

        if not isinstance(services, list):
            return Response({'error': 'services must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            serialized = []
            with transaction.atomic():
                admission_obj.services.all().delete()
                created_services = []
                for service_data in services:
                    defaults = resolve_service_defaults(service_data or {}, patient)
                    created_services.append(Service(
                        admission=admission_obj,
                        svcName=defaults['svcName'],
                        svcCode=defaults['svcCode'],  # 🌟 NEW: Saving the Code!
                        pricing_applied=defaults['pricing_applied'],
                        svcCat=defaults['svcCat'],
                        svcQty=defaults['svcQty'],
                        svcRate=defaults['svcRate'],
                        svcTot=defaults['svcTot'],
                        svcDate=defaults['svcDate'],
                    ))
                if created_services:
                    Service.objects.bulk_create(created_services)
                serialized = ServiceSerializer(admission_obj.services.order_by('svcDate', 'id'), many=True).data
            return Response({'saved': len(serialized), 'services': serialized}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    

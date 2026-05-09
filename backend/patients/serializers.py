import datetime
import re 
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from users.models import CustomUser
from .models import Doctor 
from .models import (
    Patient,
    Admission,
    MedicalHistory,
    Discharge,
    Service,
    Billing,
    ServiceMaster,
    DischargeSummary,
    Task,
    LabReport,
    HODReview,
    DepartmentLogEntry,
    ReportMaster,      
    MedicineMaster,    
    PharmacyRecord,    
    HospitalSettings,
)


def get_preferred_admission_for_patient(patient):
    if not patient:
        return None

    cached = getattr(patient, '_preferred_admission_cache', None)
    if cached is not None:
        return cached

    prefetched = getattr(patient, '_prefetched_objects_cache', {}) or {}
    admissions = prefetched.get('admissions')
    if admissions is None:
        admissions = list(patient.admissions.all())
    else:
        admissions = list(admissions)

    if not admissions:
        patient._preferred_admission_cache = None
        return None

    def is_active(admission):
        discharge = getattr(admission, 'discharge', None)
        return not getattr(discharge, 'dod', None)

    def sort_key(admission):
        timestamp = admission.dateTime.timestamp() if getattr(admission, 'dateTime', None) else 0
        return (timestamp, admission.admNo or 0, admission.id or 0)

    active_admissions = [admission for admission in admissions if is_active(admission)]
    source = active_admissions or admissions
    preferred = max(source, key=sort_key)
    patient._preferred_admission_cache = preferred
    return preferred


class MedicalHistorySerializer(serializers.ModelSerializer):
    bp_formatted = serializers.SerializerMethodField()
    spo2_formatted = serializers.SerializerMethodField()
    pr_formatted = serializers.SerializerMethodField()
    temp_formatted = serializers.SerializerMethodField()
    chest_formatted = serializers.SerializerMethodField()
    cvs_formatted = serializers.SerializerMethodField()
    cns_formatted = serializers.SerializerMethodField()
    pa_formatted = serializers.SerializerMethodField()

    class Meta:
        model = MedicalHistory
        fields = '__all__'

    def get_bp_formatted(self, obj):
        return f"{obj.bp} MMHG" if getattr(obj, 'bp', None) else ""

    def get_spo2_formatted(self, obj):
        return f"{obj.spo2} % on RA" if getattr(obj, 'spo2', None) else ""

    def get_pr_formatted(self, obj):
        # Database stores it as 'pulse', but frontend displays as PR
        return f"{obj.pulse} /MINT" if getattr(obj, 'pulse', None) else ""

    def get_temp_formatted(self, obj):
        return f"{obj.temp} °F" if getattr(obj, 'temp', None) else ""

    def get_chest_formatted(self, obj):
        return f"{obj.chest}" if getattr(obj, 'chest', None) else ""

    def get_cvs_formatted(self, obj):
        return f"{obj.cvs}" if getattr(obj, 'cvs', None) else ""

    def get_cns_formatted(self, obj):
        return f"{obj.cns}" if getattr(obj, 'cns', None) else ""

    def get_pa_formatted(self, obj):
        # Checks 'pa' or 'abd' based on what your model uses for abdomen/PA
        val = getattr(obj, 'pa', None) or getattr(obj, 'abd', None)
        return f"{val}" if val else ""

class DischargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discharge
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.admission and instance.admission.dateTime:
            local_dt = timezone.localtime(instance.admission.dateTime)
            data['doa'] = local_dt.strftime('%Y-%m-%dT%H:%M')
        return data

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        
        fields = ['id', 'svcName', 'svcCode', 'svcCat', 'svcDate', 'svcQty', 'svcRate', 'svcTot']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # 🌟 NEW: Map the database code to the frontend's 'code' variable
        data['code'] = data.get('svcCode')
        
        data['title'] = data.get('svcName')
        data['type'] = data.get('svcCat')
        data['rate'] = data.get('svcRate')
        data['qty'] = data.get('svcQty')
        data['total'] = data.get('svcTot')

        request = self.context.get('request')
        allowed_roles = ['superadmin', 'office_admin']
        
        if request and getattr(request.user, 'role', '') not in allowed_roles:
            if getattr(instance, 'pricing_applied', 'CASH') == 'CASHLESS':
                data.pop('svcRate', None)
                data.pop('svcTot', None)
                data.pop('rate', None)
                data.pop('total', None)
                
        return data

    def to_internal_value(self, data):
        resource_data = data.copy()

        if 'title' in resource_data and not resource_data.get('svcName'):
            resource_data['svcName'] = resource_data['title']
        if 'type' in resource_data and not resource_data.get('svcCat'):
            resource_data['svcCat'] = resource_data['type']
        if 'date' in resource_data and not resource_data.get('svcDate'):
            resource_data['svcDate'] = resource_data['date']

        if resource_data.get('svcDate') == "":
            resource_data['svcDate'] = None
        if not resource_data.get('svcName') or str(resource_data.get('svcName')).strip() == "":
            resource_data['svcName'] = "Service Charge" 

        try:
            raw_rate = resource_data.get('svcRate') or resource_data.get('rate') or 0
            raw_qty = resource_data.get('svcQty') or resource_data.get('qty') or 1
            rate = float(raw_rate)
            qty = int(raw_qty)
            resource_data['svcRate'] = rate
            resource_data['svcQty'] = qty
            resource_data['svcTot'] = rate * qty
        except (ValueError, TypeError):
            resource_data['svcRate'] = 0
            resource_data['svcQty'] = 1
            resource_data['svcTot'] = 0

        return super().to_internal_value(resource_data)
    
    
class BillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Billing
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')

        # 🌟 STRICT BUSINESS FLOW: Protect Billing Totals too!
        allowed_roles = ['superadmin', 'office_admin']

        if request and getattr(request.user, 'role', '') not in allowed_roles:
            if getattr(instance, 'bill_type', 'CASH') == 'CASHLESS':
                # Hide the financial totals & payments for Cashless bills from branch staff
                data.pop('paymentMode', None)
                data.pop('paidNow', None)
                data.pop('discount', None)
                data.pop('advance', None)
                
        return data
    
class AdmissionSerializer(serializers.ModelSerializer):
    medicalHistory = MedicalHistorySerializer(read_only=True)
    discharge = DischargeSerializer(read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    billing = serializers.SerializerMethodField()
    labReports = serializers.SerializerMethodField()
    pharmacyRecords = serializers.SerializerMethodField()

    class Meta:
        model = Admission
        fields = '__all__'

    def get_billing(self, obj):
        billing = obj.bills.order_by('-id').first()
        if not billing:
            return None
        return BillingSerializer(billing, context=self.context).data

    def get_labReports(self, obj):
        reports = obj.lab_reports.order_by('report_date', 'id')
        return LabReportSerializer(reports, many=True, context=self.context).data

    def get_pharmacyRecords(self, obj):
        records = obj.pharmacy_records.order_by('date_given', 'id')
        return PharmacyRecordSerializer(records, many=True, context=self.context).data
        
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.dateTime:
            local_dt = timezone.localtime(instance.dateTime)
            data['dateTime'] = local_dt.strftime('%Y-%m-%dT%H:%M')
        
        # Expose this admission's own bill_type so every dashboard
        # can read it from the admission object directly instead of patient.payMode
        billing = instance.bills.order_by('-id').first()
        data['bill_type'] = billing.bill_type if billing else 'CASH'
        return data

class PatientSerializer(serializers.ModelSerializer):
    admissions = AdmissionSerializer(many=True, read_only=True)
    current_admission_no = serializers.SerializerMethodField()
    current_admission_detail = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = '__all__'

    def get_current_admission_no(self, obj):
        admission = get_preferred_admission_for_patient(obj)
        return admission.admNo if admission else None

    def get_current_admission_detail(self, obj):
        admission = get_preferred_admission_for_patient(obj)
        if not admission:
            return None
        return AdmissionSerializer(admission, context=self.context).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        if instance.dob:
            from datetime import date
            today = date.today()
            dob = instance.dob
            
            years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
            months = today.month - dob.month
            if today.day < dob.day:
                months -= 1
            if months < 0:
                months += 12

            days = today.day - dob.day
            if days < 0:
                days += 30 
                
            data['ageYY'] = years
            data['ageMM'] = months
            data['ageDD'] = days
            
        return data
    def to_internal_value(self, data):
        date_fields = ['dob', 'tpaValidity', 'tpaPanelValidity']
        resource_data = data.copy()
        
        for field in date_fields:
            if resource_data.get(field) == "":
                resource_data[field] = None
                
        return super().to_internal_value(resource_data)
    
    def validate_phone(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        digits_only = re.sub(r'\D', '', value)
        if not value.replace('+','').replace('-','').replace(' ','').isdigit():
            raise serializers.ValidationError("Phone can only contain digits.")
        if len(digits_only) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits.")
        return value

def validate_patientName(self, value):
    if not value or not value.strip():
        raise serializers.ValidationError("Patient name is required.")
    if re.search(r'\d', value):
        raise serializers.ValidationError("Patient name cannot contain numbers.")
    return value.strip()

def validate_guardianName(self, value):
    if value and re.search(r'\d', value):
        raise serializers.ValidationError("Guardian name cannot contain numbers.")
    return value

    def validate(self, data):
        current_patient_id = self.instance.id if self.instance else None
        branch_location = str(data.get('branch_location') or getattr(self.instance, 'branch_location', '') or '').strip().upper()
        if branch_location and not HospitalSettings.objects.filter(branch=branch_location).exists():
            raise serializers.ValidationError({"branch_location": "Selected hospital branch does not exist."})
        phone = data.get('phone')
        if phone:
            phone_query = Patient.objects.filter(phone=phone)
            if current_patient_id:
                phone_query = phone_query.exclude(id=current_patient_id)
                
            if phone_query.exists():
                raise serializers.ValidationError({"error": f"A patient with phone number {phone} is already registered."})
            
        national_id = data.get('nationalId')
        if national_id:
            id_query = Patient.objects.filter(nationalId=national_id)
            if current_patient_id:
                id_query = id_query.exclude(id=current_patient_id)
                
            if id_query.exists():
                raise serializers.ValidationError({"error": f"A patient with National ID {national_id} is already registered."})

        return data


import datetime

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
class ServiceMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceMaster
        fields = '__all__'

class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = '__all__'

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
        fields = ['id', 'svcName', 'svcCat', 'svcDate', 'svcQty', 'svcRate', 'svcTot']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Your existing custom mappings for the frontend
        data['title'] = data.get('svcName')
        data['type'] = data.get('svcCat')
        data['rate'] = data.get('svcRate')
        data['qty'] = data.get('svcQty')
        data['total'] = data.get('svcTot')

        request = self.context.get('request')
        if request and getattr(request.user, 'role', '') != 'office_admin':
            if getattr(instance, 'pricing_applied', 'CASH') == 'CASHLESS':
                # Remove the database fields
                data.pop('svcRate', None)
                data.pop('svcTot', None)
                # Remove the custom frontend mapped fields
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

        if request and getattr(request.user, 'role', '') != 'office_admin':
            if getattr(instance, 'bill_type', 'CASH') == 'CASHLESS':
                data.pop('paymentMode', None)
                data.pop('paidNow', None)
                
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

    def validate(self, data):
        current_patient_id = self.instance.id if self.instance else None
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
    
class DischargeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DischargeSummary
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def get_patient_uhids(self, obj):
        return list(obj.patients.values_list('uhid', flat=True))

    def get_patient_names(self, obj):
        return list(obj.patients.values_list('patientName', flat=True))

class LabReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabReport
        fields = '__all__'
        read_only_fields = ['patient', 'admission', 'created_by', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'report_name' in data:
            data['reportName'] = data.pop('report_name')
        if 'report_type' in data:
            data['reportType'] = data.pop('report_type')
        if 'report_category' in data:
            data['reportCategory'] = data.pop('report_category')
        if 'report_date' in data:
            data['date'] = data.pop('report_date')
        if 'ordered_by' in data:
            data['orderedBy'] = data.pop('ordered_by')
        if 'modality_details' in data:
            data['modalityDetails'] = data.pop('modality_details')
        if 'table_data' in data:
            data['tests'] = data.pop('table_data')
        return data

    def to_internal_value(self, data):
        resource_data = data.copy()

        if 'reportName' in resource_data:
            resource_data['report_name'] = resource_data.pop('reportName')
        if 'reportType' in resource_data:
            resource_data['report_type'] = resource_data.pop('reportType')
        if 'reportCategory' in resource_data:
            resource_data['report_category'] = resource_data.pop('reportCategory')
        if 'date' in resource_data:
            resource_data['report_date'] = resource_data.pop('date')
        if 'orderedBy' in resource_data:
            resource_data['ordered_by'] = resource_data.pop('orderedBy')
        if 'modalityDetails' in resource_data:
            resource_data['modality_details'] = resource_data.pop('modalityDetails')
        if 'tests' in resource_data:
            resource_data['table_data'] = resource_data.pop('tests')

        if 'amount' not in resource_data:
            resource_data['amount'] = 0.00
        if 'ordered_by' not in resource_data:
            resource_data['ordered_by'] = "Doctor"
        if 'report_type' not in resource_data:
            resource_data['report_type'] = "Pathology"
        if 'report_date' not in resource_data and 'date' in data:
            resource_data['report_date'] = data.get('date')

        return super().to_internal_value(resource_data)

class HODReviewSerializer(serializers.ModelSerializer):
    employeeName = serializers.CharField(source='employee.get_full_name', read_only=True)
    employeeId = serializers.IntegerField(source='employee.id', read_only=True)
    submittedAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = HODReview
        fields = '__all__'
        read_only_fields = ['reviewed_by', 'created_at']

class DepartmentLogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartmentLogEntry
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

class ReportMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportMaster
        fields = '__all__'

class MedicineMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicineMaster
        fields = '__all__'

class PharmacyRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyRecord
        fields = '__all__'
        read_only_fields = ['patient', 'admission', 'created_by', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Convert snake_case to camelCase for the frontend
        if 'date_given' in data: data['date'] = data.pop('date_given')
        if 'medicine_name' in data: data['name'] = data.pop('medicine_name')
        if 'batch_no' in data: data['batch'] = data.pop('batch_no')
        if 'expiry_date' in data: data['expiry'] = data.pop('expiry_date')
        data['total'] = float(data.get('rate', 0)) * int(data.get('quantity', 1))
        return data

    def to_internal_value(self, data):
        resource_data = data.copy()
        # Convert frontend camelCase back to snake_case
        if 'date' in resource_data: resource_data['date_given'] = resource_data.pop('date')
        if 'name' in resource_data: resource_data['medicine_name'] = resource_data.pop('name')
        if 'batch' in resource_data: resource_data['batch_no'] = resource_data.pop('batch')
        if 'expiry' in resource_data: resource_data['expiry_date'] = resource_data.pop('expiry')
        return super().to_internal_value(resource_data)
    
class TaskSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.patientName', read_only=True)
    patient_uhid = serializers.CharField(source='patient.uhid', read_only=True)
    branch_location = serializers.CharField(source='patient.branch_location', read_only=True)
    patient_detail = PatientSerializer(source='patient', read_only=True)
    admission_no = serializers.SerializerMethodField()
    admission_detail = serializers.SerializerMethodField()
    patient_names = serializers.SerializerMethodField()
    patient_uhids = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    patients = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
    )
    assignedToId = serializers.IntegerField(write_only=True, required=False)
    patientId = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['assigned_by', 'created_at', 'updated_at']

    def get_patient_names(self, obj):
        return [obj.patient.patientName] if obj.patient else []

    def get_patient_uhids(self, obj):
        return [obj.patient.uhid] if obj.patient else []

    def get_admission_no(self, obj):
        admission = get_preferred_admission_for_patient(obj.patient)
        return admission.admNo if admission else None

    def get_admission_detail(self, obj):
        admission = get_preferred_admission_for_patient(obj.patient)
        if not admission:
            return None
        return AdmissionSerializer(admission, context=self.context).data

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return ""
        return obj.assigned_to.get_full_name().strip() or obj.assigned_to.username

    def get_assigned_by_name(self, obj):
        if not obj.assigned_by:
            return ""
        return obj.assigned_by.get_full_name().strip() or obj.assigned_by.username

    def validate(self, attrs):
        legacy_patient_ids = attrs.pop('patients', None)
        legacy_patient_uhid = attrs.pop('patientId', None)
        assigned_to_id = attrs.pop('assignedToId', None)
        patient_selection_explicit = any(
            key in self.initial_data for key in ('patient', 'patients', 'patientId')
        )

        if assigned_to_id is not None:
            assigned_to = CustomUser.objects.filter(pk=assigned_to_id).first()
            if not assigned_to:
                raise serializers.ValidationError({'assignedToId': 'Selected employee was not found.'})
            attrs['assigned_to'] = assigned_to

        if legacy_patient_ids is not None:
            if legacy_patient_ids:
                patient = Patient.objects.filter(id=legacy_patient_ids[0]).first()
                if not patient:
                    raise serializers.ValidationError({'patients': 'Selected patient was not found.'})
                attrs['patient'] = patient
            elif patient_selection_explicit:
                attrs['patient'] = None
                return attrs

        if legacy_patient_uhid is not None:
            legacy_patient_uhid = str(legacy_patient_uhid).strip()
            if legacy_patient_uhid:
                patient = Patient.objects.filter(uhid=legacy_patient_uhid).first()
                if not patient:
                    raise serializers.ValidationError({'patientId': 'Selected patient UHID was not found.'})
                attrs['patient'] = patient
            elif patient_selection_explicit and 'patient' not in attrs:
                attrs['patient'] = None

        if (
            patient_selection_explicit and
            'patient' in self.initial_data and
            self.initial_data.get('patient') in ("", None, "null")
        ):
            attrs['patient'] = None

        return attrs

class BulkTaskAssignSerializer(serializers.Serializer):
    # Accept the frontend's exact keys OR our backend keys
    assignedToId = serializers.IntegerField(required=False)
    assign_to = serializers.IntegerField(required=False)
    
    patients = serializers.ListField(child=serializers.IntegerField(), required=False)
    patient_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    
    department = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=255, required=False, default="Patient Billing Task")

    def validate(self, attrs):
        # Consolidate keys so the View knows exactly what to do
        final_assign_to = attrs.get('assignedToId') or attrs.get('assign_to')
        final_patient_ids = attrs.get('patients') or attrs.get('patient_ids')

        if not final_assign_to:
            raise serializers.ValidationError({"assign_to": "Employee ID is required."})
        if not final_patient_ids:
            raise serializers.ValidationError({"patient_ids": "At least one patient ID is required."})

        # Overwrite attrs with the standard keys expected by the View
        attrs['assign_to'] = final_assign_to
        attrs['patient_ids'] = final_patient_ids
        return attrs

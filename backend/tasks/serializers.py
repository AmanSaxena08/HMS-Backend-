from rest_framework import serializers
from django.contrib.auth import get_user_model
from users.models import CustomUser
from patients.models import Patient, Admission
from patients.serializers import PatientSerializer, AdmissionSerializer, get_preferred_admission_for_patient
from .models import Task, HODReview, DepartmentLogEntry


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
    assignedToId = serializers.IntegerField(required=False)
    assign_to = serializers.IntegerField(required=False)
    patients = serializers.ListField(child=serializers.IntegerField(), required=False)
    patient_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    department = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=255, required=False, default="Patient Billing Task")
    priority = serializers.CharField(max_length=20, required=False, default="Medium")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    due_date = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        final_assign_to = attrs.get('assignedToId') or attrs.get('assign_to')
        final_patient_ids = attrs.get('patients') or attrs.get('patient_ids')
        if not final_assign_to:
            raise serializers.ValidationError({"assign_to": "Employee ID is required."})
        if not final_patient_ids:
            raise serializers.ValidationError({"patient_ids": "At least one patient ID is required."})
        attrs['assign_to'] = final_assign_to
        attrs['patient_ids'] = final_patient_ids
        return attrs


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
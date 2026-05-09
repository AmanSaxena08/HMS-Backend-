from rest_framework import serializers
from .models import LabReport, DischargeSummary, PharmacyRecord, ReportMaster
from django.utils import timezone


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
    
class DischargeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DischargeSummary
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def get_patient_uhids(self, obj):
        return list(obj.patients.values_list('uhid', flat=True))

    def get_patient_names(self, obj):
        return list(obj.patients.values_list('patientName', flat=True))

class PharmacyRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyRecord
        fields = '__all__'
        read_only_fields = ['patient', 'admission', 'created_by', 'created_at']

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            return super().to_internal_value(data)
        resource_data = {**data}
        if 'date' in resource_data and 'date_given' not in resource_data:
            resource_data['date_given'] = resource_data.pop('date')
        if 'name' in resource_data and 'medicine_name' not in resource_data:
            resource_data['medicine_name'] = resource_data.pop('name')
        if 'batch' in resource_data and 'batch_no' not in resource_data:
            resource_data['batch_no'] = resource_data.pop('batch')
        if 'expiry' in resource_data and 'expiry_date' not in resource_data:
            resource_data['expiry_date'] = resource_data.pop('expiry')
        if resource_data.get('item') and not resource_data.get('medicine_name'):
            resource_data['medicine_name'] = resource_data.pop('item')
        elif 'item' in resource_data:
            resource_data.pop('item', None)
        if not str(resource_data.get('date_given') or '').strip():
            resource_data['date_given'] = timezone.localdate().isoformat()
        return super().to_internal_value(resource_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Convert snake_case to camelCase for the frontend
        if 'date_given' in data: data['date'] = data.pop('date_given')
        if 'medicine_name' in data: data['name'] = data.pop('medicine_name')
        if 'batch_no' in data: data['batch'] = data.pop('batch_no')
        if 'expiry_date' in data: data['expiry'] = data.pop('expiry_date')
        data['total'] = float(data.get('rate', 0)) * int(data.get('quantity', 1))
        return data

class ReportMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportMaster
        fields = '__all__'


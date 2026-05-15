from rest_framework import serializers
from .models import ServiceMaster, MedicineMaster, Doctor, HospitalSettings

class ServiceMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceMaster
        fields = '__all__'

class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['id', 'name', 'qualification', 'branch', 'created_at']

class MedicineMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicineMaster
        fields = '__all__'



class HospitalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalSettings
        fields = '__all__'

    def validate_branch(self, value):
        branch = str(value or '').strip().upper()
        if not branch:
            raise serializers.ValidationError("Branch code is required.")
        return branch

    def validate_slug(self, value):
        slug = str(value or '').strip().lower()
        if not slug:
            raise serializers.ValidationError("Branch slug is required.")
        return slug

    def validate_uhid_prefix(self, value):
        prefix = str(value or '').strip().upper()
        if not prefix:
            raise serializers.ValidationError("UHID prefix is required.")
        return prefix

    def to_internal_value(self, data):
        resource_data = data.copy()
        # Convert frontend camelCase back to snake_case
        if 'date' in resource_data: resource_data['date_given'] = resource_data.pop('date')
        if 'name' in resource_data: resource_data['medicine_name'] = resource_data.pop('name')
        if 'batch' in resource_data: resource_data['batch_no'] = resource_data.pop('batch')
        if 'expiry' in resource_data: resource_data['expiry_date'] = resource_data.pop('expiry')
        return super().to_internal_value(resource_data)
    

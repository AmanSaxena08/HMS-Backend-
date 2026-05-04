# users/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import re
from rest_framework import serializers
from .models import CustomUser
from django.db import transaction


GLOBAL_ACCESS_ROLES = {'superadmin', 'office_admin'}

def get_employee_id_prefix(role, branch):
    central_roles = [
        'office_admin', 'hod', 'billing', 'opd', 'intimation', 
        'query', 'uploading', 'nursing', 'notes', 'medical_officer', 
        'quality_analyst', 'superadmin', 'doctor' 
    ]
    if role in central_roles:
        return 'OFF'
    
    if role in ['admin', 'receptionist']:
        if branch == 'LNM':
            return 'LXM'
        if branch == 'RYM':
            return 'RAY'
            
    return 'EMP'

def generate_employee_id(role, branch):
    prefix = get_employee_id_prefix(role, branch)
    with transaction.atomic():
        users = (
            CustomUser.objects
            .select_for_update()
            .filter(emp_id__startswith=prefix)
            .values_list('emp_id', flat=True)
        )
        highest = 0
        for emp_id in users:
            suffix = str(emp_id)[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f"{prefix}{highest + 1:04d}"


def get_access_scope(user):
    return 'all_hospitals' if user.role in GLOBAL_ACCESS_ROLES or user.branch == 'ALL' else 'single_branch'


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['branch'] = user.branch
        token['access_scope'] = get_access_scope(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['branch'] = self.user.branch
        data['access_scope'] = get_access_scope(self.user)
        data['username'] = self.user.username
        data['name'] = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return data
    
class UserManagementSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    access_scope = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'role', 'branch', 'emp_id', 'phone_number', 
            'password', 'confirm_password', 'is_active', 'access_scope',
            'date_joined', 'last_login',
        ]

    def get_access_scope(self, obj):
        return get_access_scope(obj)

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if ' ' in value:
            raise serializers.ValidationError("Password cannot contain spaces.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def validate(self, data):
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        branch = str(data.get('branch') or getattr(self.instance, 'branch', '') or '').strip().upper()
        role = str(data.get('role') or getattr(self.instance, 'role', 'receptionist')).strip()
        emp_id = str(data.get('emp_id') or getattr(self.instance, 'emp_id', '') or '').strip().upper()
        
        expected_prefix = get_employee_id_prefix(role, branch)

        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required."})

        if password or confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if self.instance is None:
            if emp_id and expected_prefix and not emp_id.startswith(expected_prefix):
                raise serializers.ValidationError({"emp_id": f"Employee ID must start with {expected_prefix}."})
            if not emp_id:
                data['emp_id'] = generate_employee_id(role, branch)
            elif emp_id:
                data['emp_id'] = emp_id
        elif emp_id:
            if expected_prefix and not emp_id.startswith(expected_prefix):
                raise serializers.ValidationError({"emp_id": f"Employee ID must start with {expected_prefix}."})
            data['emp_id'] = emp_id
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(password=password, **validated_data)
        return user

    def update(self, instance, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        instance.save()
        return instance
    
class AdminPasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_new_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        if len(value) < 8 or ' ' in value or not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password does not meet security requirements.")
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class VerifyOTPandResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_new_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        if len(value) < 8 or ' ' in value or not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must be 8+ chars, no spaces, and have a special character.")
        return value

    def validate(self, data):
        if data.get('new_password') != data.get('confirm_new_password'):
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        return data

class SelfProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'phone_number', 'emp_id', 'role', 'branch',
        ]
        read_only_fields = ['id', 'username', 'role', 'branch']
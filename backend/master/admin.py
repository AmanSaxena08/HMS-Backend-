from django.contrib import admin
from .models import ServiceMaster, MedicineMaster, Doctor, HospitalSettings


@admin.register(HospitalSettings)
class HospitalSettingsAdmin(admin.ModelAdmin):
    list_display = ('hospital_name', 'branch', 'branch_name', 'phone')
    list_filter = ('branch',)

    def has_add_permission(self, request):
        # Allow multiple branches but warn if branch already exists
        return True


@admin.register(ServiceMaster)
class ServiceMasterAdmin(admin.ModelAdmin):
    list_display = ('description', 'category', 'pricing_type', 'code', 'rate')
    list_filter = ('category', 'pricing_type')
    search_fields = ('description', 'code')


@admin.register(MedicineMaster)
class MedicineMasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'batch_no', 'expiry_date', 'rate', 'quantity')
    search_fields = ('name', 'batch_no')


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'qualification', 'created_at')
    search_fields = ('name',)
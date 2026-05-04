from django.contrib import admin
from .models import Patient, Admission, MedicalHistory, Discharge, Service, Billing, ServiceMaster, DischargeSummary, Task, LabReport, HODReview, DepartmentLogEntry, ReportMaster, MedicineMaster, PharmacyRecord
from django.contrib import admin
from .models import HospitalSettings

# This creates a nice table view for your Patients in the Admin panel
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('uhid', 'patientName', 'phone', 'created_at')
    search_fields = ('uhid', 'patientName', 'phone')

# This creates a nice table view for your Admissions
@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    # 🌟 Removed 'admissionDate' from here so the server boots up perfectly
    list_display = ('ipdNo', 'patient', 'admNo') 
    search_fields = ('ipdNo', 'patient__uhid')

# Registering the rest of your models so they show up!
admin.site.register(ServiceMaster)
admin.site.register(Service)
admin.site.register(Billing)
admin.site.register(Discharge)
admin.site.register(MedicalHistory)
admin.site.register(ReportMaster)
admin.site.register(MedicineMaster)
admin.site.register(PharmacyRecord)


@admin.register(HospitalSettings)
class HospitalSettingsAdmin(admin.ModelAdmin):
    list_display = ('hospital_name', 'branch', 'branch_name', 'phone')
    list_filter = ('branch',)

    def has_add_permission(self, request):
        # 🌟 SINGLETON LOCK: Prevent adding a second settings row if one already exists
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
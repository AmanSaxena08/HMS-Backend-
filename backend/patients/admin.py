from django.contrib import admin
from .models import Patient, Admission, MedicalHistory, Discharge, Service, Billing


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('uhid', 'patientName', 'phone', 'branch_location', 'payMode', 'created_at')
    search_fields = ('uhid', 'patientName', 'phone')
    list_filter = ('branch_location', 'payMode', 'gender')


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ('ipdNo', 'patient', 'admNo', 'dateTime')
    search_fields = ('ipdNo', 'patient__uhid', 'patient__patientName')
    list_filter = ('dateTime',)


admin.site.register(Service)
admin.site.register(Billing)
admin.site.register(Discharge)
admin.site.register(MedicalHistory)
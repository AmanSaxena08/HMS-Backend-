from django.contrib import admin
from .models import LabReport, DischargeSummary, PharmacyRecord, ReportMaster


@admin.register(LabReport)
class LabReportAdmin(admin.ModelAdmin):
    list_display = ('report_name', 'report_type', 'patient', 'report_date', 'created_at')
    search_fields = ('report_name', 'patient__uhid', 'patient__patientName')
    list_filter = ('report_type', 'report_date')


@admin.register(DischargeSummary)
class DischargeSummaryAdmin(admin.ModelAdmin):
    list_display = ('admission', 'summary_type', 'created_at', 'updated_at')
    list_filter = ('summary_type',)


@admin.register(PharmacyRecord)
class PharmacyRecordAdmin(admin.ModelAdmin):
    list_display = ('medicine_name', 'patient', 'batch_no', 'quantity', 'rate', 'date_given')
    search_fields = ('medicine_name', 'patient__uhid', 'batch_no')


admin.site.register(ReportMaster)
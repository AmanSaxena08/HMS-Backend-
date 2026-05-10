from django.db import models
from django.conf import settings
from patients.models import Admission, Patient


class LabReport(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_reports')
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='lab_reports', null=True, blank=True)

    report_name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=100, blank=True)
    report_category = models.CharField(max_length=50, blank=True)
    report_date = models.DateField(null=True, blank=True)
    ordered_by = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True)
    modality_details = models.JSONField(default=dict, blank=True)
    table_data = models.JSONField(default=list)
    text_data = models.JSONField(default=list, blank=True)
    created_by = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.report_name} for {self.patient.uhid}"


class ReportMaster(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class DischargeSummary(models.Model):
    STATUS_CHOICES = [
        ('NORMAL', 'Normal'),
        ('LAMA', 'LAMA'),
        ('REFERRED', 'Referred'),
        ('DEATH', 'Death'),
        ('DOPR', 'dopr'),
    ]

    admission = models.OneToOneField(Admission, on_delete=models.CASCADE, related_name='dynamic_summary')
    summary_type = models.CharField(max_length=20, choices=STATUS_CHOICES)
    content = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.summary_type} Summary for Adm No: {self.admission.admNo} (UHID: {self.admission.patient.uhid})"


class PharmacyRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pharmacy_records')
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='pharmacy_records')
    date_given = models.CharField(max_length=50)
    medicine_name = models.CharField(max_length=255)
    batch_no = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.medicine_name} for {self.patient.uhid}"
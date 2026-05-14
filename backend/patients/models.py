from django.db import models
from django.utils import timezone
import datetime
from django.conf import settings
from users.models import CustomUser
from django.db import transaction
from core.utils import get_default_branch_code, get_branch_settings

class Patient(models.Model):
    branch_location = models.CharField(max_length=10, default='LNM')
    uhid = models.CharField(max_length=25, unique=True, blank=True)
    
    patientName = models.CharField(max_length=150)
    guardianName = models.CharField(max_length=150)
    gender = models.CharField(max_length=15)
    dob = models.DateField(null=True, blank=True)
    bloodGroup = models.CharField(max_length=10, blank=True)
    maritalStatus = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=15)
    altPhone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    nationalId = models.CharField(max_length=50)
    remarks = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    payMode = models.CharField(max_length=20)
    cashlessType = models.CharField(max_length=20, blank=True)
    tpa = models.CharField(max_length=100, blank=True)
    tpaCard = models.CharField(max_length=50, blank=True)
    tpaValidity = models.DateField(null=True, blank=True)
    tpaCardType = models.CharField(max_length=50, blank=True)
    tpaPanelCardNo = models.CharField(max_length=50, blank=True)
    tpaPanelValidity = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.branch_location:
            self.branch_location = get_default_branch_code()
        self.branch_location = str(self.branch_location).upper()

        if not self.uhid:
            branch_settings = get_branch_settings(self.branch_location)
            prefix = (branch_settings.uhid_prefix or self.branch_location or "SH").upper()
            with transaction.atomic():
                last_patient = (
                    Patient.objects
                    .select_for_update()
                    .filter(branch_location=self.branch_location)
                    .order_by('id')
                    .last()
                )
                if last_patient and last_patient.uhid:
                    try:
                        # Use [-1] not [1] — handles both old (SHL-000-1) and new (SHL-0000001) format
                        last_number = int(last_patient.uhid.split("-")[-1])
                        new_number = last_number + 1
                    except (IndexError, ValueError):
                        new_number = 1
                else:
                    new_number = 1
                self.uhid = f"{prefix}-{str(new_number).zfill(7)}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

class Admission(models.Model):
    ADMISSION_TYPE_CHOICES = (
        ('IPD', 'IPD'),
        ('OPD', 'OPD'),
        ('DayCare', 'Day Care'),
    )

    PAY_MODE_CHOICES = (
        ('cash', 'Cash'),
        ('cashless', 'Cashless'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='admissions')
    ipdNo = models.CharField(max_length=50, unique=True, blank=True)
    admNo = models.PositiveIntegerField()
    admissionType = models.CharField(max_length=20, choices=ADMISSION_TYPE_CHOICES, default='IPD')
    # Per-admission paymode — set by receptionist at registration/re-admission time.
    # Drives billing bill_type and service pricing. Independent of Patient.payMode.
    payMode = models.CharField(max_length=20, choices=PAY_MODE_CHOICES, default='cash')
    dateTime = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-admNo']
        unique_together = ('patient', 'admNo')
        indexes = [
            models.Index(fields=['patient', 'admNo']),
            models.Index(fields=['payMode']),
        ] 

    def __str__(self):
        return f"{self.patient.uhid} - Adm #{self.admNo} ({self.ipdNo})"
    
    def save(self, *args, **kwargs):
        if not self.ipdNo:
            year = datetime.datetime.now().strftime('%y')
            prefix = f"SH/GEN/{year}/"
            with transaction.atomic():
                # Sort by -id (integer) not -ipdNo (string) — string sort breaks after 9999
                last_admission = (
                    Admission.objects
                    .select_for_update()
                    .filter(ipdNo__startswith=prefix)
                    .order_by('-id')
                    .first()
                )
                if last_admission:
                    try:
                        last_sequence = int(last_admission.ipdNo.split('/')[-1])
                        new_sequence = last_sequence + 1
                    except (ValueError, IndexError):
                        new_sequence = 1001
                else:
                    new_sequence = 1001
                self.ipdNo = f"{prefix}{new_sequence}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

class MedicalHistory(models.Model):
    admission = models.OneToOneField(Admission, related_name='medicalHistory', on_delete=models.CASCADE)
    bp = models.CharField(max_length=50, blank=True, null=True)
    spo2 = models.CharField(max_length=50, blank=True, null=True)
    pulse = models.CharField(max_length=50, blank=True, null=True)  # PR
    pr = models.CharField(max_length=50, blank=True, null=True)
    temp = models.CharField(max_length=50, blank=True, null=True)
    chest = models.CharField(max_length=100, blank=True, null=True)
    cvs = models.CharField(max_length=100, blank=True, null=True)
    cns = models.CharField(max_length=100, blank=True, null=True)
    pa = models.CharField(max_length=100, blank=True, null=True)
    previousDiagnosis = models.TextField(blank=True)
    pastSurgeries = models.TextField(blank=True)
    currentMedications = models.TextField(blank=True)
    investigations = models.TextField(blank=True, null=True)
    presentComplaints = models.TextField(blank=True, null=True)
    chiefComplaints = models.TextField(blank=True, null=True)
    provisionalDiagnosis = models.TextField(blank=True, null=True)
    treatmentAdvised = models.TextField(blank=True, null=True)
    customList = models.JSONField(default=list, blank=True)
    treatingDoctor = models.CharField(max_length=150, blank=True)
    knownAllergies = models.TextField(blank=True)
    chronicConditions = models.TextField(blank=True)
    familyHistory = models.TextField(blank=True)
    smokingStatus = models.CharField(max_length=50, blank=True)
    alcoholUse = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

class Discharge(models.Model):
    admission = models.OneToOneField(Admission, related_name='discharge', on_delete=models.CASCADE)

    department = models.CharField(max_length=100, blank=True)
    doctorName = models.CharField(max_length=150, blank=True)
    wardName = models.CharField(max_length=100, blank=True)
    roomNo = models.CharField(max_length=50, blank=True)
    bedNo = models.CharField(max_length=50, blank=True)
    diagnosis = models.TextField(blank=True)
    doa = models.DateTimeField(null=True, blank=True) 

    expectedDod = models.DateField(null=True, blank=True)
    dod = models.DateTimeField(null=True, blank=True)
    dischargeStatus = models.CharField(max_length=100, blank=True)
    instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)

class Service(models.Model):    
    admission = models.ForeignKey('Admission', related_name='services', on_delete=models.CASCADE)
    pricing_applied = models.CharField(max_length=10, default='CASH')
    svcName = models.CharField(max_length=200)
    svcCode = models.CharField(max_length=50, blank=True, default='')
    svcCat = models.CharField(max_length=100, blank=True)
    svcDate = models.DateField(null=True, blank=True)
    svcQty = models.PositiveIntegerField(default=1)
    svcRate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    svcTot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class Meta:
        ordering = ['svcDate', 'id']
        indexes = [
            models.Index(fields=['admission', 'svcDate']),
            models.Index(fields=['pricing_applied']),
        ]

class Billing(models.Model):
    admission = models.OneToOneField(
        Admission, on_delete=models.CASCADE,
        related_name='billing'  # Changed from 'bills' to 'billing' (one-to-one is singular)
    )
    
    BILL_TYPE_CHOICES = [
        ('CASH', 'Cash'),
        ('CASHLESS', 'Cashless'),
    ]
    bill_type = models.CharField(max_length=20, choices=BILL_TYPE_CHOICES, default='CASH') # ✨ NEW
    
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)
    paymentMode = models.CharField(max_length=50, blank=True)
    insuranceType = models.CharField(max_length=100, blank=True)
    tpaInfo = models.JSONField(default=dict, blank=True)
    tpaDocStatus = models.JSONField(default=dict, blank=True)
    paidNow = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    printStatus = models.CharField(max_length=50, default='DRAFT') 
    printRequestedAt = models.DateTimeField(null=True, blank=True)


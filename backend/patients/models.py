from django.db import models
from django.utils import timezone
import datetime
from django.conf import settings
from users.models import CustomUser


class Patient(models.Model):
    BRANCH_CHOICES = [('LNM', 'Laxmi Nagar'), ('RYM', 'Raya')]
    branch_location = models.CharField(max_length=3, choices=BRANCH_CHOICES, default='LNM')
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
    
    payMode = models.CharField(max_length=20, default='cash')
    cashlessType = models.CharField(max_length=20, blank=True)
    tpa = models.CharField(max_length=100, blank=True)
    tpaCard = models.CharField(max_length=50, blank=True)
    tpaValidity = models.DateField(null=True, blank=True)
    tpaCardType = models.CharField(max_length=50, blank=True)
    tpaPanelCardNo = models.CharField(max_length=50, blank=True)
    tpaPanelValidity = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.uhid:
            # 1. Determine the prefix based on the branch
            prefix = "SHL" if self.branch_location == "LNM" else "SHR"
            
            # 2. Safely find the last patient registered in this specific branch
            last_patient = Patient.objects.filter(branch_location=self.branch_location).order_by('id').last()
            
            if last_patient and last_patient.uhid:
                try:
                    # Extract the numeric part (e.g., "0000001" from "SHL-0000001")
                    last_number_str = last_patient.uhid.split("-")[1]
                    last_number = int(last_number_str)
                    new_number = last_number + 1
                except (IndexError, ValueError):
                    # Fallback if the previous UHID format was weird
                    new_number = 1
            else:
                # If this is the very first patient for this branch
                new_number = 1
            
            # 3. Format the new number with 7 digits (e.g., 1 becomes "0000001")
            formatted_number = str(new_number).zfill(7)
            
            # 4. Construct the final UHID
            self.uhid = f"{prefix}-{formatted_number}"
            
        super().save(*args, **kwargs)

class Admission(models.Model):
    ADMISSION_TYPE_CHOICES = (
        ('IPD', 'IPD'),
        ('OPD', 'OPD'),
        ('DayCare', 'Day Care'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='admissions')
    ipdNo = models.CharField(max_length=50, unique=True, blank=True)
    admNo = models.PositiveIntegerField()
    admissionType = models.CharField(max_length=20, choices=ADMISSION_TYPE_CHOICES, default='IPD')
    dateTime = models.DateTimeField(default=timezone.now) 
    
    class Meta:
        unique_together = ('patient', 'admNo') 

    def __str__(self):
        return f"{self.patient.uhid} - Adm #{self.admNo} ({self.ipdNo})"

    @property
    def billing(self):
        return self.bills.order_by('-id').first()
    
    def save(self, *args, **kwargs):
        if not self.ipdNo:
            year = datetime.datetime.now().strftime('%y')
            prefix = f"SH/GEN/{year}/"
            last_admission = Admission.objects.filter(
                ipdNo__startswith=prefix
            ).order_by('-ipdNo').first()
            
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

class MedicalHistory(models.Model):
    admission = models.OneToOneField(Admission, related_name='medicalHistory', on_delete=models.CASCADE)
    previousDiagnosis = models.TextField(blank=True)
    pastSurgeries = models.TextField(blank=True)
    currentMedications = models.TextField(blank=True)
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
    svcCat = models.CharField(max_length=100, blank=True)
    svcDate = models.DateField(null=True, blank=True)
    svcQty = models.PositiveIntegerField(default=1)
    svcRate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    svcTot = models.DecimalField(max_digits=10, decimal_places=2, default=0)

class Billing(models.Model):
    admission = models.ForeignKey('Admission', related_name='bills', on_delete=models.CASCADE)
    
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

class ServiceMaster(models.Model):
    CATEGORY_CHOICES = [
        ('ICU CARE', 'ICU Care'),
        ('ROOM CHARGE', 'Room Charge'),
        ('CONSULTANT', 'Consultant'),
        ('RADIOLOGY', 'Radiology'),
        ('GENERAL SERVICES', 'General Services'),
    ]
    
    PRICING_CHOICES = [
        ('CASH', 'Cash'),
        ('CASHLESS', 'Cashless'),
    ]
    
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    pricing_type = models.CharField(max_length=10, choices=PRICING_CHOICES, default='CASH') 
    description = models.TextField()
    code = models.CharField(max_length=50, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"[{self.category}] {self.description} ({self.pricing_type})"

class DischargeSummary(models.Model):

    STATUS_CHOICES = [
        ('NORMAL', 'Normal'),
        ('LAMA', 'LAMA'),
        ('REFERRED', 'Referred'),
        ('DEATH', 'Death'),
        ('DOPR', 'dopr'),
    ]

    # Links directly to your existing Admission model
    admission = models.OneToOneField(Admission, on_delete=models.CASCADE, related_name='dynamic_summary')
    
    summary_type = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # This JSON field holds the entire generated/edited template form
    content = models.JSONField(default=dict) 
    
    # Audit tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.summary_type} Summary for Adm No: {self.admission.admNo} (UHID: {self.admission.patient.uhid})"
    
class Task(models.Model):
    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('On Hold', 'On Hold'),
        ('Overdue', 'Overdue'),
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Who assigned it? (Office Admin or HOD)
    assigned_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='tasks_given')
    
    # Who is doing it? (HOD or Staff)
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tasks_received')
    
    # Which department does this task belong to?
    department = models.CharField(max_length=100) 
    
    # 🌟 SINGLE PATIENT TRACKING: 1 Task = 1 Patient
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='assigned_tasks', null=True, blank=True)
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    due_date = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"

class LabReport(models.Model):
    # Link it to the patient and the specific admission
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_reports')
    admission = models.ForeignKey('Admission', on_delete=models.CASCADE, related_name='lab_reports', null=True, blank=True)
    
    report_name = models.CharField(max_length=255) # e.g., "KIDNEY FUNCTION TEST"
    report_type = models.CharField(max_length=100, blank=True)
    report_category = models.CharField(max_length=50, blank=True)
    report_date = models.DateField(null=True, blank=True)
    ordered_by = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True)
    modality_details = models.JSONField(default=dict, blank=True)
    
    # Stores the table rows [{"name": "BLOOD UREA", "value": "47", "normal": "(13-45 mg/dl)"}]
    table_data = models.JSONField(default=list)
    
    # Stores the pre-filled paragraphs [{"title": "COMMENTS", "text": "The typhidot test..."}]
    text_data = models.JSONField(default=list, blank=True)
    
    created_by = models.CharField(max_length=255, blank=True, null=True) # E.g., the receptionist's name
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.report_name} for {self.patient.uhid}"

class HODReview(models.Model):
    PERIOD_CHOICES = (
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )

    department = models.CharField(max_length=100)
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hod_reviews')
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_hod_reviews')
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='weekly')
    rating = models.PositiveSmallIntegerField(default=5)
    performance_score = models.CharField(max_length=100, blank=True)
    comments = models.TextField(blank=True)
    task_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.username} review ({self.department})"

class DepartmentLogEntry(models.Model):
    DEPARTMENT_CHOICES = (
        ('opd', 'OPD'),
        ('intimation', 'Intimation'),
        ('query', 'Query'),
        ('uploading', 'Uploading'),
    )

    BRANCH_CHOICES = (
        ('LNM', 'Laxmi Nagar'),
        ('RYM', 'Raya'),
    )

    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    branch = models.CharField(max_length=10, choices=BRANCH_CHOICES, default='LNM')
    record_date = models.DateField()
    data = models.JSONField(default=dict)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='department_logs_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-record_date', '-created_at']

    def __str__(self):
        return f"{self.department} log ({self.branch}) - {self.record_date}"

class ReportMaster(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class MedicineMaster(models.Model):
    name = models.CharField(max_length=255)
    batch_no = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.name} - {self.batch_no}"

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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.medicine_name} for {self.patient.uhid}"

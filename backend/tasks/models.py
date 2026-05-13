from django.db import models
from django.db.models import ForeignKey, CASCADE, SET_NULL
from django.conf import settings
from patients.models import Patient, Admission  
from users.models import CustomUser
from core.utils import get_default_branch_code


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
    
    # SINGLE PATIENT TRACKING: 1 Task = 1 Patient
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='assigned_tasks', null=True, blank=True)
    
    # ════════════════════════════════════════════════════════════════════════════════
    # PHASE 6 IMPROVEMENT — Per-Admission Task Assignment
    # ════════════════════════════════════════════════════════════════════════════════
    # Specific admission this task is for. If null, defaults to latest active admission.
    # This prevents confusion when a patient has multiple admissions (re-visits).
    #
    # Example:
    #   Task 1: Patient X, Admission 1 → Staff works on admission 1
    #   Task 2: Patient X, Admission 2 → Staff works on admission 2 (not confused with admission 1)
    admission = models.ForeignKey(
        Admission, 
        on_delete=models.CASCADE, 
        related_name='tasks',
        null=True, 
        blank=True,
        help_text="Specific admission this task is for. If null, defaults to latest active admission."
    )
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    due_date = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'assigned_to']),
            models.Index(fields=['admission', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"
    
    def get_active_admission(self):
        """
        Returns the admission for this task.
        If admission is explicitly set, use it. Otherwise, use latest admission.
        """
        if self.admission:
            return self.admission
        return self.patient.admissions.order_by('-admNo').first() if self.patient else None

    
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
        ('billing', 'Billing'),             
        ('nursing', 'Nursing'),             
        ('doctor', 'Doctor'),               
        ('notes', 'Notes'),                 
        ('quality_analyst', 'Quality Analysis'), 
        ('medical_officer', 'Medical Officer'),  
    )

    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    branch = models.CharField(max_length=10, default='LNM')
    record_date = models.DateField()
    data = models.JSONField(default=dict)
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='department_logs_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-record_date', '-created_at']

    def save(self, *args, **kwargs):
        self.branch = str(self.branch or get_default_branch_code()).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.department} log ({self.branch}) - {self.record_date}"
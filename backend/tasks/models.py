from django.db import models
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
    
    # 🌟 SINGLE PATIENT TRACKING: 1 Task = 1 Patient
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='assigned_tasks', null=True, blank=True)
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    due_date = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"
    
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
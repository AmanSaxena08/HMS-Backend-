from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import datetime

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('admin', 'Branch Admin'),
        ('office_admin', 'Office Admin'),
        ('receptionist', 'Receptionist'),
        ('billing', 'Billing'),
        ('hod', 'HOD'),
        ('opd', 'OPD'),
        ('intimation', 'Intimation'),
        ('query', 'Query'),
        ('uploading', 'Uploading'),
    )

    BRANCH_CHOICES = (
        ('LNM', 'Laxmi Nagar'),
        ('RYM', 'Raya'),
        ('ALL', 'All Branches'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='receptionist')
    branch = models.CharField(max_length=10, choices=BRANCH_CHOICES, null=True, blank=True)
    emp_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.emp_id:
            role_prefixes = {
                'office_admin': 'OFF', 'hod': 'HOD', 'billing': 'BIL',
                'opd': 'OPD', 'intimation': 'INT', 'query': 'QRY',
                'uploading': 'UPL', 'receptionist': 'REC', 'admin': 'ADM', 'superadmin': 'SUP'
            }
            prefix = role_prefixes.get(self.role, 'EMP')
            last_user = CustomUser.objects.filter(emp_id__startswith=prefix).order_by('id').last()
            
            if last_user and last_user.emp_id:
                try:
                    last_num = int(last_user.emp_id.replace(prefix, ""))
                    new_num = last_num + 1
                except (ValueError, TypeError):
                    new_num = 1
            else:
                new_num = 1
            
            self.emp_id = f"{prefix}{str(new_num).zfill(4)}"
            
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
class PasswordResetOTP(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        expiration_time = self.created_at + datetime.timedelta(minutes=10)
        return timezone.now() <= expiration_time and not self.is_used

    def __str__(self):
        return f"{self.user.username} - {self.otp}"
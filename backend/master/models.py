from django.db import models
from django.db import models
from django.conf import settings  
from core.utils import get_default_branch_code, get_branch_settings
# Create your models here.

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
    
class MedicineMaster(models.Model):
    name = models.CharField(max_length=255)
    batch_no = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} - {self.batch_no}"

class Doctor(models.Model):
    name = models.CharField(max_length=255)
    qualification = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.qualification}"

class HospitalSettings(models.Model):
    branch = models.CharField(max_length=10, unique=True, default='LNM')
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    uhid_prefix = models.CharField(max_length=10, default='SHL')
    hospital_name = models.CharField(max_length=255, default="SANGI HOSPITAL")
    branch_name = models.CharField(max_length=255, default="Lakshmi Nagar Branch")
    address = models.TextField(default="Lakshmi Nagar, Mathura, Uttar Pradesh - 281004")
    phone = models.CharField(max_length=150, default="+91-9717444531 / +91-9717444532")
    email = models.EmailField(default="laxminagar@sangihospital.com")
    website = models.URLField(default="https://www.sangihospital.com")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)

    def save(self, *args, **kwargs):
        self.branch = str(self.branch or '').upper()
        if not self.slug:
            self.slug = str(self.branch_name or self.branch or '').strip().lower().replace('&', 'and').replace('/', '-').replace(' ', '-')
        self.slug = str(self.slug).strip().lower()
        if not self.uhid_prefix:
            self.uhid_prefix = (self.branch or 'SH')[:3].upper()
        self.uhid_prefix = str(self.uhid_prefix).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.hospital_name} - {self.branch_name}"

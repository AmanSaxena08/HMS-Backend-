# backend/master/urls.py - ADD PREVIEW ENDPOINT URL

# ============ ADD THIS TO urlpatterns ============

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ServiceMasterViewSet,
    MedicineMasterViewSet,
    DoctorViewSet,
    HospitalSettingsViewSet,
    MedicineMasterImportAPIView,
    MedicineMasterPreviewAPIView,  # ADD THIS IMPORT
    AdminDashboardStatsAPIView,
)

router = DefaultRouter()
router.register(r'services', ServiceMasterViewSet, basename='service-master')
router.register(r'medicines', MedicineMasterViewSet, basename='medicine-master')
router.register(r'doctors', DoctorViewSet, basename='doctor')
router.register(r'hospital-settings', HospitalSettingsViewSet, basename='hospital-settings')

urlpatterns = [
    path('', include(router.urls)),
    path('medicines/import/', MedicineMasterImportAPIView.as_view(), name='medicine-import'),
    path('medicines/preview/', MedicineMasterPreviewAPIView.as_view(), name='medicine-preview'),  # ADD THIS LINE
    path('admin-stats/', AdminDashboardStatsAPIView.as_view(), name='admin-stats'),
]
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ServiceMasterViewSet,
    HospitalSettingsViewSet,
    MedicineMasterViewSet,
    MedicineMasterImportAPIView,
    DoctorViewSet,
    AdminDashboardStatsAPIView,
)

router = DefaultRouter()
router.register(r'service-master', ServiceMasterViewSet, basename='service-master')
router.register(r'hospital-settings', HospitalSettingsViewSet, basename='hospital-settings')
router.register(r'medicine-master', MedicineMasterViewSet, basename='medicine-master')
router.register(r'doctors', DoctorViewSet, basename='doctor')

urlpatterns = router.urls + [
    path('medicine-master/import-excel/', MedicineMasterImportAPIView.as_view(), name='medicine-master-import-excel'),
    path('admin/dashboard/stats/', AdminDashboardStatsAPIView.as_view(), name='admin-dashboard-stats'),
]
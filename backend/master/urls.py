# ============================================================
# FILE: backend/master/urls.py
# ACTION: FULL REPLACE — paste this entire file
# ============================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ServiceMasterViewSet,
    MedicineMasterViewSet,
    DoctorViewSet,
    HospitalSettingsViewSet,
    MedicineMasterImportAPIView,
    MedicineMasterPreviewAPIView,
    AdminDashboardStatsAPIView,
)

router = DefaultRouter()
router.register(r'service-master',   ServiceMasterViewSet,  basename='service-master')
router.register(r'medicine-master',  MedicineMasterViewSet, basename='medicine-master')
router.register(r'doctors',          DoctorViewSet,         basename='doctor')
router.register(r'hospital-settings', HospitalSettingsViewSet, basename='hospital-settings')

urlpatterns = [
    path('', include(router.urls)),
    path('medicine-master/import/',   MedicineMasterImportAPIView.as_view(),  name='medicine-import'),
    path('medicine-master/preview/',  MedicineMasterPreviewAPIView.as_view(), name='medicine-preview'),
    path('admin-stats/',              AdminDashboardStatsAPIView.as_view(),    name='admin-stats'),
]
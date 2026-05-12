from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    PatientViewSet,
    ServiceBulkSaveAPIView,
)

router = DefaultRouter()
router.register(r'patients', PatientViewSet)

urlpatterns = router.urls + [
    path('patients/<str:uhid>/admissions/<str:adm_no>/services/bulk-save/', ServiceBulkSaveAPIView.as_view(), name='services-bulk-save'),
]

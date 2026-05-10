from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    LabReportListCreateView,
    LabReportBulkSaveAPIView,
    LabReportTemplateSuggestionsAPIView,
    DynamicDischargeSummaryView,
    PrintDischargeSummaryView,
    PrintBillView,
    PrintAdmissionNoteView,
    PrintMedicalHistoryView,
    PrintLabReportsView,
    PrintPharmacyRecordsView,
    PharmacyRecordViewSet,
    PharmacyRecordBulkSaveAPIView,
    CanonicalRecordsAPIView,
    ReportMasterViewSet,
)

router = DefaultRouter()
router.register(r'report-master', ReportMasterViewSet, basename='report-master')

urlpatterns = router.urls + [
    # ── Lab reports ────────────────────────────────────────────────────────────
    path('patients/<str:uhid>/admissions/<int:adm_no>/lab-reports/', LabReportListCreateView.as_view(), name='lab-reports'),
    path('patients/<str:uhid>/admissions/<int:adm_no>/lab-report-templates/', LabReportTemplateSuggestionsAPIView.as_view(), name='lab-report-templates'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/lab-reports/bulk-save/', LabReportBulkSaveAPIView.as_view(), name='lab-reports-bulk-save'),

    # ── Pharmacy records ───────────────────────────────────────────────────────
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/', PharmacyRecordViewSet.as_view({'get': 'list', 'post': 'create'}), name='pharmacy-records-list'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/bulk-save/', PharmacyRecordBulkSaveAPIView.as_view(), name='pharmacy-records-bulk-save'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/<int:pk>/', PharmacyRecordViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='pharmacy-records-detail'),

    # ── Discharge summary ──────────────────────────────────────────────────────
    path('patients/<str:uhid>/admissions/<str:adm_no>/dynamic-summary/', DynamicDischargeSummaryView.as_view(), name='dynamic-summary'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/dynamic-summary/print/', PrintDischargeSummaryView.as_view(), name='print-summary'),

    # ── PDF printing ───────────────────────────────────────────────────────────
    path('patients/<str:uhid>/admissions/<str:adm_no>/bill/print/', PrintBillView.as_view(), name='print-bill'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/admission-note/print/', PrintAdmissionNoteView.as_view(), name='print-admission-note'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/medical-history/print/', PrintMedicalHistoryView.as_view(), name='print-medical-history'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/lab-reports/print/', PrintLabReportsView.as_view(), name='print-lab-reports'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/print/', PrintPharmacyRecordsView.as_view(), name='print-pharmacy-records'),

    # ── Canonical records ──────────────────────────────────────────────────────
    path('patients/<str:uhid>/admissions/<str:adm_no>/canonical-records/', CanonicalRecordsAPIView.as_view(), name='canonical-records'),
]
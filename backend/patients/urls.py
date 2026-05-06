from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    PatientViewSet,
    PrintDischargeSummaryView,
    ServiceMasterViewSet,
    DynamicDischargeSummaryView,
    TaskListCreateAPIView,
    TaskDetailAPIView,
    TaskReportAPIView,
    HODEmployeeListAPIView,
    HODTaskListCreateAPIView,
    HODTaskDetailAPIView,
    HODAnalyticsAPIView,
    HODReviewListCreateAPIView,
    HODReportDownloadAPIView,
    PerformanceRatingsAPIView,
    DepartmentLogListAPIView,
    DepartmentLogBulkSaveAPIView,
    ServiceBulkSaveAPIView,
    LabReportListCreateView,
    LabReportBulkSaveAPIView,
    LabReportTemplateSuggestionsAPIView,
    PharmacyRecordBulkSaveAPIView,
    DoctorViewSet, 
    PrintBillView,
    MedicineMasterImportAPIView,
)

router = DefaultRouter()
router.register(r'patients', PatientViewSet)
router.register(r'service-master', ServiceMasterViewSet)
router.register(r'hospital-settings', views.HospitalSettingsViewSet, basename='hospital-settings')
router.register(r'report-master', views.ReportMasterViewSet, basename='report-master')
router.register(r'medicine-master', views.MedicineMasterViewSet, basename='medicine-master')
router.register(r'doctors', DoctorViewSet, basename='doctor') 



urlpatterns = [
    path('patients/<str:uhid>/admissions/<str:adm_no>/dynamic-summary/', DynamicDischargeSummaryView.as_view(), name='dynamic-summary'),
    path('patients/pending_prints/', PatientViewSet.as_view({'get': 'pending_prints'}), name='patients-pending-prints'),
    path('', include(router.urls)),
    path('patients/<str:uhid>/admissions/<str:adm_no>/dynamic-summary/print/', PrintDischargeSummaryView.as_view(), name='print-summary'),
    path('hod/employees/', HODEmployeeListAPIView.as_view(), name='hod-employees'),
    path('hod/tasks/', HODTaskListCreateAPIView.as_view(), name='hod-tasks'),
    path('hod/tasks/<int:pk>/', HODTaskDetailAPIView.as_view(), name='hod-task-detail'),
    path('hod/analytics/', HODAnalyticsAPIView.as_view(), name='hod-analytics'),
    path('hod/reviews/', HODReviewListCreateAPIView.as_view(), name='hod-reviews'),
    path('hod/reports/download/', HODReportDownloadAPIView.as_view(), name='hod-reports-download'),
    path('hod/performance-ratings/', PerformanceRatingsAPIView.as_view(), name='hod-performance-ratings'),
    path('department-logs/', DepartmentLogListAPIView.as_view(), name='department-logs'),
    path('department-logs/bulk-save/', DepartmentLogBulkSaveAPIView.as_view(), name='department-logs-bulk-save'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/services/bulk-save/', ServiceBulkSaveAPIView.as_view(), name='services-bulk-save'),
    path('tasks/', TaskListCreateAPIView.as_view(), name='task-list-create'),
    path('tasks/<int:pk>/', TaskDetailAPIView.as_view(), name='task-detail'),
    path('tasks/report/', TaskReportAPIView.as_view(), name='task-report'),
    path('patients/<str:uhid>/admissions/<int:adm_no>/lab-reports/', LabReportListCreateView.as_view(), name='lab-reports'),
    path('patients/<str:uhid>/admissions/<int:adm_no>/lab-report-templates/', LabReportTemplateSuggestionsAPIView.as_view(), name='lab-report-templates'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/lab-reports/bulk-save/', LabReportBulkSaveAPIView.as_view(), name='lab-reports-bulk-save'),
    path('medicine-master/import-excel/', MedicineMasterImportAPIView.as_view(), name='medicine-master-import-excel'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/', views.PharmacyRecordViewSet.as_view({'get': 'list', 'post': 'create'}), name='pharmacy-records-list'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/bulk-save/', PharmacyRecordBulkSaveAPIView.as_view(), name='pharmacy-records-bulk-save'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/pharmacy-records/<int:pk>/', views.PharmacyRecordViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='pharmacy-records-detail'),
    path('tasks/eligible-employees/', views.TaskEligibleEmployeesAPIView.as_view(), name='task-eligible-employees'),
    path('tasks/bulk-assign/', views.BulkTaskAssignAPIView.as_view(), name='task-bulk-assign'),
    path('tasks/analytics/', views.TaskAnalyticsAPIView.as_view(), name='task-analytics'),
    path('tasks/<int:task_id>/update-status/', views.EmployeeTaskUpdateAPIView.as_view(), name='task-update-status'),
    path('tasks/my-tasks/', views.EmployeeMyTasksAPIView.as_view(), name='task-my-tasks'),
    path('patients/<str:uhid>/admissions/<str:adm_no>/bill/print/', PrintBillView.as_view(), name='print-bill'),
]

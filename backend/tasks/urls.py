from django.urls import path
from .views import (
    TaskListCreateAPIView,
    TaskDetailAPIView,
    TaskReportAPIView,
    TaskEligibleEmployeesAPIView,
    BulkTaskAssignAPIView,
    TaskAnalyticsAPIView,
    EmployeeTaskUpdateAPIView,
    EmployeeMyTasksAPIView,
    HODEmployeeListAPIView,
    HODTaskListCreateAPIView,
    HODTaskDetailAPIView,
    HODAnalyticsAPIView,
    HODReviewListCreateAPIView,
    HODReportDownloadAPIView,
    PerformanceRatingsAPIView,
    DepartmentLogListAPIView,
    DepartmentLogBulkSaveAPIView,
)

urlpatterns = [
    # ── General tasks ──────────────────────────────────────────────────────────
    path('tasks/', TaskListCreateAPIView.as_view(), name='task-list-create'),
    path('tasks/report/', TaskReportAPIView.as_view(), name='task-report'),
    path('tasks/eligible-employees/', TaskEligibleEmployeesAPIView.as_view(), name='task-eligible-employees'),
    path('tasks/bulk-assign/', BulkTaskAssignAPIView.as_view(), name='task-bulk-assign'),
    path('tasks/analytics/', TaskAnalyticsAPIView.as_view(), name='task-analytics'),
    path('tasks/my-tasks/', EmployeeMyTasksAPIView.as_view(), name='task-my-tasks'),
    path('tasks/<int:pk>/', TaskDetailAPIView.as_view(), name='task-detail'),
    path('tasks/<int:task_id>/update-status/', EmployeeTaskUpdateAPIView.as_view(), name='task-update-status'),

    # ── HOD ────────────────────────────────────────────────────────────────────
    path('hod/employees/', HODEmployeeListAPIView.as_view(), name='hod-employees'),
    path('hod/tasks/', HODTaskListCreateAPIView.as_view(), name='hod-tasks'),
    path('hod/tasks/<int:pk>/', HODTaskDetailAPIView.as_view(), name='hod-task-detail'),
    path('hod/analytics/', HODAnalyticsAPIView.as_view(), name='hod-analytics'),
    path('hod/reviews/', HODReviewListCreateAPIView.as_view(), name='hod-reviews'),
    path('hod/reports/download/', HODReportDownloadAPIView.as_view(), name='hod-reports-download'),
    path('hod/performance-ratings/', PerformanceRatingsAPIView.as_view(), name='hod-performance-ratings'),

    # ── Department logs ────────────────────────────────────────────────────────
    path('department-logs/', DepartmentLogListAPIView.as_view(), name='department-logs'),
    path('department-logs/bulk-save/', DepartmentLogBulkSaveAPIView.as_view(), name='department-logs-bulk-save'),
]
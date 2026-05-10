from django.contrib import admin
from .models import Task, HODReview, DepartmentLogEntry


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'assigned_by', 'patient', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'department')
    search_fields = ('title', 'assigned_to__username', 'patient__uhid')


@admin.register(HODReview)
class HODReviewAdmin(admin.ModelAdmin):
    list_display = ('employee', 'reviewed_by', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('employee__username',)


@admin.register(DepartmentLogEntry)
class DepartmentLogEntryAdmin(admin.ModelAdmin):
    list_display = ('department', 'created_by', 'record_date', 'created_at')
    list_filter = ('department',)
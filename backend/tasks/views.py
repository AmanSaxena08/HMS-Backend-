from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from users import permissions
from patients.models import Patient, Admission
from .models import Task, HODReview, DepartmentLogEntry
from .serializers import TaskSerializer, BulkTaskAssignSerializer, HODReviewSerializer, DepartmentLogEntrySerializer
from users.models import CustomUser
# Create your views here.

class TaskListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_task_queryset_for_user(self.request.user)

    def perform_create(self, serializer):
        assigned_to = serializer.validated_data['assigned_to']
        patient = serializer.validated_data.get('patient')
        department = serializer.validated_data.get('department')
        validate_generic_task_assignment(
            self.request.user,
            assigned_to,
            patient=patient,
            department=department,
        )
        serializer.save(assigned_by=self.request.user)


class TaskDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_task_queryset_for_user(self.request.user)

    def perform_update(self, serializer):
        user = self.request.user

        # 🌟 THE BYPASS: If a regular employee is just clicking "Submit"
        if user.role not in TASK_MANAGER_ROLES:
            # Security check: Make sure they aren't trying to maliciously re-assign the task
            if 'assigned_to' in serializer.validated_data or 'department' in serializer.validated_data or 'patient' in serializer.validated_data:
                raise PermissionDenied("Employees cannot re-assign tasks or change departments.")
            
            # If they are just updating status (like "Completed") or adding notes, let it save!
            serializer.save()
            return

        # 👔 THE MANAGER CHECK: If an Admin/HOD is editing, run the strict validation
        assigned_to = serializer.validated_data.get('assigned_to', serializer.instance.assigned_to)
        patient = serializer.validated_data.get('patient', serializer.instance.patient)
        department = serializer.validated_data.get('department', serializer.instance.department)
        
        validate_generic_task_assignment(
            user,
            assigned_to,
            patient=patient,
            department=department,
        )
        serializer.save()

class TaskReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ['superadmin', 'office_admin', 'admin', 'hod']:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        staff = CustomUser.objects.filter(role__in=[
    'billing', 'opd', 'intimation', 'query', 'uploading', 'hod',
    'nursing', 'notes', 'medical_officer', 'quality_analyst',
])
        if request.user.role == 'admin':
            staff = staff.filter(branch=request.user.branch)
        
        report_data = []
        for employee in staff:
            total_tasks = employee.tasks_received.count()
            completed_tasks = employee.tasks_received.filter(status='Completed').count()
            
            assigned_patients = Patient.objects.filter(assigned_tasks__assigned_to=employee).distinct()
            patient_list = [{"uhid": p.uhid, "name": p.patientName} for p in assigned_patients]

            if total_tasks > 0:
                report_data.append({
                    "employee_name": f"{employee.first_name} {employee.last_name}",
                    "department": employee.role,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "pending_tasks": total_tasks - completed_tasks,
                    "assigned_patients": patient_list
                })

        return Response(report_data)

class TaskEligibleEmployeesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        department = request.query_params.get('department')

        if user.role == 'superadmin':
            employees = CustomUser.objects.filter(role__in=TASK_ASSIGNABLE_ROLES | {'admin', 'office_admin'})
        elif user.role == 'office_admin':
            employees = CustomUser.objects.filter(role__in=TASK_ASSIGNABLE_ROLES)
        elif user.role == 'admin':
            employees = CustomUser.objects.filter(role__in=TASK_ASSIGNABLE_ROLES, branch=user.branch)
        elif user.role == 'hod':
            role_slug = get_department_role(department)
            if not role_slug:
                return Response({"error": "Invalid department."}, status=status.HTTP_400_BAD_REQUEST)
            employees = CustomUser.objects.filter(role=role_slug)
        if getattr(user, 'branch', None) in get_valid_branch_codes():
                employees = employees.filter(branch=user.branch)
        else:
            employees = CustomUser.objects.none()

        data = [{"id": emp.id, "name": emp.get_full_name().strip() or emp.username, "role": emp.get_role_display()} for emp in employees]
        return Response(data)
    
class BulkTaskAssignAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Check if user is in the updated TASK_MANAGER_ROLES
        if request.user.role not in TASK_MANAGER_ROLES:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        serializer = BulkTaskAssignSerializer(data=request.data)
        if serializer.is_valid():
            assign_to_id = serializer.validated_data['assign_to']
            patient_ids = serializer.validated_data['patient_ids']
            department = serializer.validated_data['department']
            title = serializer.validated_data.get('title', 'Patient Task')
            priority = serializer.validated_data.get('priority', 'Medium')
            notes = serializer.validated_data.get('notes', '')
            due_date = serializer.validated_data.get('due_date')

            try:
                assigned_to_user = CustomUser.objects.get(id=assign_to_id)
            except CustomUser.DoesNotExist:
                return Response({"error": "Assigned user not found."}, status=status.HTTP_404_NOT_FOUND)

            try:
                validate_generic_task_assignment(request.user, assigned_to_user)
            except PermissionDenied as exc:
                return Response({"error": str(exc.detail)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as exc:
                return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

            tasks_to_create = []
            for pid in patient_ids:
                try:
                    patient = Patient.objects.get(id=pid)
                    

                    validate_generic_task_assignment(
                        request.user,
                        assigned_to_user,
                        patient=patient,
                    )
                    
                    tasks_to_create.append(
                        Task(
                            title=title,
                            description=notes,
                            assigned_by=request.user,
                            assigned_to=assigned_to_user,
                            department=department,
                            patient=patient,
                            status='Pending',
                            priority=priority,
                            due_date=due_date,
                        )
                    )
                except ValidationError as exc:
                    return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
                except Patient.DoesNotExist:
                    continue

            Task.objects.bulk_create(tasks_to_create)
            
            return Response(
                {"message": f"Successfully assigned {len(tasks_to_create)} patients to {assigned_to_user.username}."}, 
                status=status.HTTP_201_CREATED
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TaskAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 👇 FIXED: Using exact database role keys (lowercase)
        if user.role not in ['superadmin', 'office_admin', 'hod']:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        if user.role == 'hod':
            qs = Task.objects.filter(assigned_by=user)
        else:
            qs = Task.objects.all()

        # 👇 FIXED: Changed assigned_to__name to assigned_to__username
        analytics = qs.values(
            'assigned_to__id', 
            'assigned_to__username', 
            'assigned_to__role'
        ).annotate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=Q(status='Completed')),
            pending_tasks=Count('id', filter=Q(status='Pending'))
        )
        return Response(analytics)
    
class EmployeeTaskUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response({"error": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        
        user = request.user
        is_admin_or_hod = user.role in ['superadmin', 'office_admin', 'hod']

        # 1. Authorization: Must be the assigned employee OR an admin/hod
        if task.assigned_to != user and not is_admin_or_hod:
            return Response({"error": "Not authorized to update this task."}, status=status.HTTP_403_FORBIDDEN)

        # 2. 🌟 THE LOCK: Block employee if completed, but let Admin/HOD bypass
        if task.status == 'Completed' and not is_admin_or_hod:
            return Response(
                {"error": "This task is already submitted and locked. Only an HOD or Admin can edit it now."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 3. Normalize Status
        raw_status = str(request.data.get('status', task.status)).strip().title()
        if raw_status.lower() == 'completed':
            raw_status = 'Completed'
        elif raw_status.lower() in ['in progress', 'inprogress']:
            raw_status = 'In Progress'

        valid_statuses = ['Pending', 'In Progress', 'Completed', 'On Hold', 'Overdue']
        
        if raw_status in valid_statuses:
            task.status = raw_status
            
            # 4. Capture the work & label who wrote it
            work_done = request.data.get('work_done') or request.data.get('remarks') or request.data.get('notes')
            if work_done:
                role_label = "HOD/Admin" if is_admin_or_hod else "Employee"
                if task.description:
                    task.description = f"{task.description}\n\n[{role_label} Update]: {work_done}"
                else:
                    task.description = f"[{role_label} Update]: {work_done}"

            task.save()
            return Response({
                "message": "Task updated successfully!", 
                "status": task.status,
                "notes": task.description
            }, status=status.HTTP_200_OK)
            
        return Response({"error": f"Invalid status. Must be one of {valid_statuses}"}, status=status.HTTP_400_BAD_REQUEST)

class EmployeeMyTasksAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tasks = get_task_queryset_for_user(request.user)
        
        # Sort logic: 
        # 1. Pending (Value 1) comes first, then everything else (Value 2)
        # 2. Older tasks come first ('created_at' ascending)
        tasks = tasks.annotate(
    status_order=Case(
        When(status='Pending', then=Value(1)),
        When(status='In Progress', then=Value(2)), 
        When(status='Overdue', then=Value(3)),
        default=Value(4),                             
        output_field=IntegerField(),
    )
).order_by('status_order', 'created_at')

        serializer = TaskSerializer(tasks, many=True, context={'request': request})
        return Response(serializer.data)
    
class HODEmployeeListAPIView(APIView):
    def get(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        department = request.query_params.get('department')
        role_slug = get_department_role(department)
        if not role_slug:
            return Response({'error': 'Invalid department.'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = CustomUser.objects.filter(role=role_slug)

        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            queryset = queryset.filter(branch=request.user.branch)

        queryset = (queryset | CustomUser.objects.filter(pk=request.user.pk)).distinct()

        employees = []
        for employee in queryset.order_by('first_name', 'username'):
            tasks = employee.tasks_received.filter(department=department)
            employee_name = employee.get_full_name().strip() or employee.username
            employees.append({
                'id': employee.id,
                'employeeCode': employee.emp_id or employee.username,
                'name': employee_name,
                'email': employee.email,
                'role': employee.role,
                'department': department,
                'taskCount': tasks.count(),
            })

        return Response({'employees': employees}, status=status.HTTP_200_OK)

class HODTaskListCreateAPIView(APIView):
    def get(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        department = request.query_params.get('department')
        role_slug = get_department_role(department)
        if not role_slug:
            return Response({'error': 'Invalid department.'}, status=status.HTTP_400_BAD_REQUEST)
        employee_id = request.query_params.get('employeeId')
        date_filter = request.query_params.get('date')
        status_filter = request.query_params.get('status')

        tasks = Task.objects.select_related('assigned_to', 'patient').filter(
            models.Q(department=department) | models.Q(assigned_to=request.user)
        )

        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            tasks = tasks.filter(
                models.Q(assigned_to__branch=request.user.branch) |
                models.Q(assigned_to__branch__isnull=True)
            )

        if employee_id:
            tasks = tasks.filter(assigned_to_id=employee_id)
        if date_filter:
            tasks = tasks.filter(created_at__date=date_filter)

        serialized = [serialize_task_for_hod(task) for task in tasks.order_by('-created_at')]
        if status_filter:
            serialized = [task for task in serialized if task['status'] == status_filter]

        return Response({'tasks': serialized}, status=status.HTTP_200_OK)

    def post(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        employee_id = request.data.get('employeeId')
        department = request.data.get('department')
        role_slug = get_department_role(department)
        if not role_slug:
            return Response({'error': 'Invalid department.'}, status=status.HTTP_400_BAD_REQUEST)
        assigned_to = get_object_or_404(CustomUser, pk=employee_id)
        if assigned_to.pk != request.user.pk and assigned_to.role != role_slug:
            return Response({'error': 'Selected employee does not belong to this department.'}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(request.user, 'branch', None) in get_valid_branch_codes() and assigned_to.branch != request.user.branch:
            return Response({'error': 'You can assign tasks only inside your own branch.'}, status=status.HTTP_403_FORBIDDEN)
        due_date_raw = request.data.get('dueDate')
        due_date = None
        if due_date_raw:
            due_date = timezone.make_aware(datetime.datetime.fromisoformat(f"{due_date_raw}T23:59:00"))

        patient = None
        patient_uhid = request.data.get('patientId')
        if patient_uhid:
            patient = Patient.objects.filter(uhid=patient_uhid).first()
            if not patient:
                return Response({'error': 'Selected patient was not found.'}, status=status.HTTP_400_BAD_REQUEST)
            if assigned_to.branch in get_valid_branch_codes() and patient.branch_location != assigned_to.branch:
                return Response({'error': 'Selected patient belongs to a different branch.'}, status=status.HTTP_400_BAD_REQUEST)

        priority_map = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}
        task = Task.objects.create(
            title=request.data.get('taskType') or 'Task',
            description=request.data.get('notes') or '',
            assigned_by=request.user,
            assigned_to=assigned_to,
            department=department,
            priority=priority_map.get(str(request.data.get('priority')).lower(), 'Medium'),
            status=normalize_task_status(request.data.get('status') or 'pending', due_date),
            due_date=due_date,
            patient=patient,
        )

        return Response({'task': serialize_task_for_hod(task)}, status=status.HTTP_201_CREATED)

class HODTaskDetailAPIView(APIView):
    def patch(self, request, pk):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        task = get_object_or_404(Task, pk=pk)
        due_date = task.due_date
        if 'priority' in request.data:
            priority_map = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}
            task.priority = priority_map.get(str(request.data.get('priority')).lower(), task.priority)
        if 'notes' in request.data:
            task.description = request.data.get('notes') or ''
        if 'status' in request.data:
            task.status = normalize_task_status(request.data.get('status'), due_date)
        task.save()
        return Response({'task': serialize_task_for_hod(task)}, status=status.HTTP_200_OK)

class HODAnalyticsAPIView(APIView):
    def get(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        department = request.query_params.get('department')
        role_slug = get_department_role(department)
        if not role_slug:
            return Response({'error': 'Invalid department.'}, status=status.HTTP_400_BAD_REQUEST)
        employee_id = request.query_params.get('employeeId')
        date_filter = request.query_params.get('date')

        tasks = Task.objects.select_related('assigned_to', 'patient').filter(department=department)
        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            tasks = tasks.filter(assigned_to__branch=request.user.branch)
        if employee_id:
            tasks = tasks.filter(assigned_to_id=employee_id)
        if date_filter:
            tasks = tasks.filter(created_at__date=date_filter)

        task_rows = [serialize_task_for_hod(task) for task in tasks]
        total = len(task_rows)
        completed = sum(1 for task in task_rows if task['status'] == 'completed')
        pending = sum(1 for task in task_rows if task['status'] == 'pending')
        overdue = sum(1 for task in task_rows if task['status'] == 'overdue')

        stats = [
            {'label': 'Total Tasks', 'value': total, 'sub': f'{department or "All"} department'},
            {'label': 'Completed', 'value': completed, 'sub': 'Marked complete'},
            {'label': 'Pending', 'value': pending, 'sub': 'Awaiting action'},
            {'label': 'Overdue', 'value': overdue, 'sub': 'Past due date'},
        ]

        employee_stats = []
        employee_queryset = CustomUser.objects.filter(role=role_slug)
        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            employee_queryset = employee_queryset.filter(branch=request.user.branch)
        for employee in employee_queryset:
            employee_tasks = [task for task in task_rows if task['employeeId'] == employee.id]
            if not employee_tasks and employee_id:
                continue
            assigned = len(employee_tasks)
            emp_completed = sum(1 for task in employee_tasks if task['status'] == 'completed')
            emp_pending = sum(1 for task in employee_tasks if task['status'] == 'pending')
            emp_overdue = sum(1 for task in employee_tasks if task['status'] == 'overdue')
            employee_stats.append({
                'id': employee.id,
                'name': employee.get_full_name().strip() or employee.username,
                'assigned': assigned,
                'completed': emp_completed,
                'pending': emp_pending,
                'overdue': emp_overdue,
                'completionPct': int(round((emp_completed / assigned) * 100)) if assigned else 0,
            })

        return Response({'stats': stats, 'employeeStats': employee_stats}, status=status.HTTP_200_OK)

class HODReviewListCreateAPIView(APIView):
    def get(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        department = request.query_params.get('department')
        reviews = HODReview.objects.select_related('employee', 'reviewed_by').filter(department=department).order_by('-created_at')

        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            reviews = reviews.filter(employee__branch=request.user.branch)

        payload = []
        for review in reviews:
            payload.append({
                'id': review.id,
                'employeeName': review.employee.get_full_name().strip() or review.employee.username,
                'employeeId': review.employee_id,
                'period': review.period,
                'rating': review.rating,
                'performanceScore': review.performance_score,
                'comments': review.comments,
                'submittedAt': timezone.localtime(review.created_at).strftime('%Y-%m-%d %H:%M'),
            })
        return Response({'reviews': payload}, status=status.HTTP_200_OK)

    def post(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        employee = get_object_or_404(CustomUser, pk=request.data.get('employeeId'))
        review = HODReview.objects.create(
            department=request.data.get('department') or '',
            employee=employee,
            reviewed_by=request.user,
            period=request.data.get('period') or 'weekly',
            rating=int(request.data.get('rating') or 5),
            performance_score=str(request.data.get('performanceScore') or ''),
            comments=request.data.get('comments') or '',
            task_name=request.data.get('taskName') or 'Department Performance',
        )
        serializer = HODReviewSerializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class HODReportDownloadAPIView(APIView):
    def get(self, request):
        denied = ensure_hod_access(request)
        if denied:
            return denied

        department = request.query_params.get('department')
        role_slug = get_department_role(department)
        if not role_slug:
            return Response({'error': 'Invalid department.'}, status=status.HTTP_400_BAD_REQUEST)
        employee_id = request.query_params.get('employeeId')
        date_filter = request.query_params.get('date')

        tasks = Task.objects.select_related('assigned_to', 'patient').filter(department=department)
        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            tasks = tasks.filter(assigned_to__branch=request.user.branch)
        if employee_id:
            tasks = tasks.filter(assigned_to_id=employee_id)
        if date_filter:
            tasks = tasks.filter(created_at__date=date_filter)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{quote((department or "department").lower())}_tasks_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Task ID', 'Employee', 'Task', 'Patient UHID', 'Priority', 'Status', 'Due Date'])
        for task in tasks.order_by('-created_at'):
            data = serialize_task_for_hod(task)
            writer.writerow([
                data['id'],
                data['employeeName'],
                data['taskType'],
                data['patientId'],
                data['priority'],
                data['status'],
                data['dueDate'],
            ])
        return response

class PerformanceRatingsAPIView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Unauthorized access.'}, status=status.HTTP_401_UNAUTHORIZED)

        reviews = HODReview.objects.select_related('employee', 'reviewed_by').order_by('-created_at')
        payload = []
        for review in reviews:
            branch_obj = HospitalSettings.objects.filter(branch=review.employee.branch).first()
            branch = branch_obj.slug if branch_obj else str(review.employee.branch or '').lower()
            payload.append({
                'staffName': review.employee.get_full_name().strip() or review.employee.username,
                'staffId': review.employee.emp_id or review.employee.username,
                'branch': branch,
                'role': review.employee.get_role_display(),
                'department': review.department,
                'task': review.task_name or 'Department Performance',
                'rating': review.rating,
                'reviewedBy': review.reviewed_by.get_full_name().strip() if review.reviewed_by else 'System',
                'description': review.comments,
                'reason': '',
                'date': timezone.localtime(review.created_at).date().isoformat(),
            })
        return Response(payload, status=status.HTTP_200_OK)

class DepartmentLogListAPIView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Unauthorized access.'}, status=status.HTTP_401_UNAUTHORIZED)

        department = request.query_params.get('department')
        queryset = DepartmentLogEntry.objects.filter(department=department)

        if getattr(request.user, 'branch', None) in get_valid_branch_codes():
            queryset = queryset.filter(branch=request.user.branch)

        serializer = DepartmentLogEntrySerializer(queryset.order_by('-record_date', '-created_at'), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DepartmentLogBulkSaveAPIView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Unauthorized access.'}, status=status.HTTP_401_UNAUTHORIZED)

        department = request.data.get('department')
        entries = request.data.get('entries') or []
        if department not in dict(DepartmentLogEntry.DEPARTMENT_CHOICES):
            return Response({'error': 'Invalid department.'}, status=status.HTTP_400_BAD_REQUEST)

        branch = getattr(request.user, 'branch', None) if getattr(request.user, 'branch', None) in get_valid_branch_codes() else resolve_branch_code_from_loc(None, request.data.get('branch'))
        record_dates = sorted({coerce_record_date(department, entry) for entry in entries})

        with transaction.atomic():
            if record_dates:
                DepartmentLogEntry.objects.filter(
                    department=department,
                    branch=branch,
                    record_date__in=record_dates,
                ).delete()

            created = []
            for entry in entries:
                created.append(DepartmentLogEntry(
                    department=department,
                    branch=branch,
                    record_date=coerce_record_date(department, entry),
                    data=entry,
                    created_by=request.user,
                ))
            if created:
                DepartmentLogEntry.objects.bulk_create(created)

        return Response({'saved': len(entries)}, status=status.HTTP_200_OK)

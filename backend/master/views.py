import os, base64, io, openpyxl
import datetime
import logging
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from users import permissions
from users.models import CustomUser
from patients.models import Patient, Admission, Service, Billing, Discharge
from tasks.models import Task
from core.utils import get_branch_settings_queryset
from .models import ServiceMaster, MedicineMaster, Doctor, HospitalSettings
from .serializers import ServiceMasterSerializer, MedicineMasterSerializer, DoctorSerializer, HospitalSettingsSerializer

logger = logging.getLogger(__name__)


class ServiceMasterViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ServiceMasterSerializer
    pagination_class = None

    def get_queryset(self):
        qs = ServiceMaster.objects.all()
        pricing = self.request.query_params.get('pricing_type')
        if pricing:
            qs = qs.filter(pricing_type=pricing.upper())
        return qs


class HospitalSettingsViewSet(viewsets.ModelViewSet):
    queryset = get_branch_settings_queryset()
    serializer_class = HospitalSettingsSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        if getattr(request.user, 'role', '') != 'superadmin':
            raise PermissionDenied("Only Super Admin can create hospital branches.")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if getattr(request.user, 'role', '') != 'superadmin':
            raise PermissionDenied("Only Super Admin can update hospital branches.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, 'role', '') != 'superadmin':
            raise PermissionDenied("Only Super Admin can delete hospital branches.")
        instance = self.get_object()
        if Patient.objects.filter(branch_location=instance.branch).exists():
            raise ValidationError({'branch': 'This branch already has patient records and cannot be deleted.'})
        if CustomUser.objects.filter(branch=instance.branch).exists():
            raise ValidationError({'branch': 'This branch already has user accounts and cannot be deleted.'})
        return super().destroy(request, *args, **kwargs)


class MedicineMasterViewSet(viewsets.ModelViewSet):
    queryset = MedicineMaster.objects.all().order_by('name')
    serializer_class = MedicineMasterSerializer
    permission_classes = [IsAuthenticated]


def parse_medicine_master_workbook(uploaded_file):
    def normalize_expiry_date(value):
        if value in (None, ''):
            return None

        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value

        text = str(value).strip()
        if not text:
            return None

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        for fmt in ("%m/%Y", "%m-%Y", "%m/%y", "%m-%y"):
            try:
                parsed = datetime.datetime.strptime(text, fmt)
                return datetime.date(parsed.year, parsed.month, 1)
            except ValueError:
                continue

        return None

    workbook = openpyxl.load_workbook(uploaded_file, data_only=True)
    worksheet = workbook[workbook.sheetnames[0]]

    header_row_index = None
    headers = []
    for index, row in enumerate(worksheet.iter_rows(min_row=1, max_row=min(25, worksheet.max_row), values_only=True), start=1):
        normalized = [str(cell).strip().lower() if cell is not None else '' for cell in row]
        if 'description' in normalized and 'rate' in normalized and ('qty.' in normalized or 'qty' in normalized):
            header_row_index = index
            headers = [str(cell).strip() if cell is not None else '' for cell in row]
            break

    if not header_row_index:
        raise ValidationError({'file': "Could not find medicine sheet headers. Expected columns like Description, Batch No., Exp., Rate, Qty."})

    parsed_rows = []
    for row in worksheet.iter_rows(min_row=header_row_index + 1, values_only=True):
        row_map = {headers[idx]: row[idx] if idx < len(row) else None for idx in range(len(headers))}

        description = str(row_map.get('Description') or '').strip()
        if not description or description.lower() in {'none', 'nan'}:
            continue

        batch_no = str(row_map.get('Batch No.') or '').strip()
        expiry_date = normalize_expiry_date(row_map.get('Exp.'))
        rate_raw = row_map.get('Rate')
        qty_raw = row_map.get('Qty.') if 'Qty.' in row_map else row_map.get('Qty')

        try:
            rate = Decimal(str(rate_raw or 0)).quantize(Decimal('0.01'))
        except Exception:
            rate = Decimal('0.00')

        try:
            quantity = int(float(qty_raw or 0))
        except Exception:
            quantity = 0

        parsed_rows.append(
            MedicineMaster(
                name=description,
                batch_no=batch_no or None,
                expiry_date=expiry_date,
                rate=rate,
                quantity=max(quantity, 0),
            )
        )

    if not parsed_rows:
        raise ValidationError({'file': 'No medicine rows were found in the uploaded sheet.'})

    return parsed_rows


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 6 IMPROVEMENT — MedicineMaster Preview Endpoint
# ════════════════════════════════════════════════════════════════════════════════

class MedicineMasterPreviewAPIView(APIView):
    """
    Preview endpoint for medicine master import.
    Validates the file and returns a sample WITHOUT committing to DB.
    
    Usage:
        POST /api/master/medicines/preview/
        Body: FormData with 'file' field
        
    Returns:
        {
            "total_rows": 150,
            "preview_rows": [...first 10 medicines...],
            "message": "Preview: 150 medicines will be imported. Click 'Confirm Import' to finalize."
        }
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if getattr(request.user, 'role', '') not in {'superadmin', 'office_admin'}:
            raise PermissionDenied("Only Super Admin and Office Admin can preview medicine imports.")

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            raise ValidationError({'file': 'Please upload an Excel file.'})

        try:
            rows = parse_medicine_master_workbook(uploaded_file)
            
            return Response(
                {
                    'total_rows': len(rows),
                    'preview_rows': MedicineMasterSerializer(rows[:10], many=True).data,
                    'message': f'Preview: {len(rows)} medicines will be imported. Click "Confirm Import" to finalize.',
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            raise e
        except Exception as e:
            logger.exception('Medicine import preview failed')
            raise ValidationError({'file': f'Failed to parse file: {str(e)}'})


class MedicineMasterImportAPIView(APIView):
    """
    Import endpoint for medicine master.
    Requires 'confirmed=true' from frontend after preview is reviewed.
    
    Usage:
        POST /api/master/medicines/import/
        Body: FormData with 'file' field and 'confirmed' parameter
        
    Returns:
        {
            "imported": 150,
            "replaced": 120,
            "message": "Medicine master updated successfully.",
            "sample": [...first 10 medicines...]
        }
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if getattr(request.user, 'role', '') not in {'superadmin', 'office_admin'}:
            raise PermissionDenied("Only Super Admin and Office Admin can import medicine records.")

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            raise ValidationError({'file': 'Please upload an Excel file.'})

        # Check for confirmation from frontend
        is_confirmed = str(request.data.get('confirmed', 'false')).lower() == 'true'
        
        if not is_confirmed:
            return Response(
                {
                    'warning': 'Please preview the file first before importing.',
                    'message': 'Use the preview endpoint to validate your file.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rows = parse_medicine_master_workbook(uploaded_file)

            with transaction.atomic():
                deleted_count = MedicineMaster.objects.count()
                MedicineMaster.objects.all().delete()
                MedicineMaster.objects.bulk_create(rows)

            return Response(
                {
                    'imported': len(rows),
                    'replaced': deleted_count,
                    'message': 'Medicine master updated successfully.',
                    'sample': MedicineMasterSerializer(MedicineMaster.objects.all().order_by('name')[:10], many=True).data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception('Medicine master import failed')
            raise ValidationError({'file': f'Import failed: {str(e)}'})


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all().order_by('name')
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            if getattr(request.user, 'role', '') not in ['superadmin', 'admin', 'office_admin']:
                self.permission_denied(request, message="Only Admins can manage the doctors list.")


class AdminDashboardStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        if user.role not in ['superadmin', 'office_admin', 'admin']:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        
        todays_discharges = Discharge.objects.filter(dod__date=today)

        if user.role == 'admin':
            todays_discharges = todays_discharges.filter(admission__patient__branch_location=user.branch)

        return Response({
            "todaysDischargeCount": todays_discharges.count(),
        }, status=status.HTTP_200_OK)
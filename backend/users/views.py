from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from rest_framework import generics
from .models import CustomUser
from .serializers import UserManagementSerializer, SelfProfileSerializer
from .permissions import IsBranchAdminOrSuperAdmin
from rest_framework.response import Response
from rest_framework import status
from .serializers import AdminPasswordResetSerializer
import random
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import PasswordResetOTP
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import api_view, permission_classes



CENTRAL_STAFF_ROLES = {
    'billing', 'hod', 'opd', 'intimation', 'query',
    'uploading', 'nursing', 'notes', 'medical_officer', 'quality_analyst', 'doctor'
}
BRANCH_STAFF_ROLES = {'receptionist'}

# Combine them for general checks
STAFF_ROLES = CENTRAL_STAFF_ROLES | BRANCH_STAFF_ROLES
SUPERADMIN_MANAGED_ROLES = STAFF_ROLES | {'admin', 'office_admin'}
BRANCH_CODES = {'LNM', 'RYM'}
ALL_BRANCH_CODE = 'ALL'

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_emp_id(request):
    user = request.user
    

    if user.role == 'admin':
        role = 'receptionist'
        branch = user.branch
    else:
        role = request.query_params.get('role', 'receptionist')
        branch = request.query_params.get('branch', 'LNM')
        
    central_roles = [
        'office_admin', 'hod', 'billing', 'opd', 'intimation', 
        'query', 'uploading', 'nursing', 'notes', 'medical_officer', 
        'quality_analyst', 'superadmin', 'doctor' 
    ]
    
    if role in central_roles:
        prefix = 'OFF'
    elif role in ['admin', 'receptionist']:
        prefix = 'LXM' if branch == 'LNM' else 'RAY' if branch == 'RYM' else 'EMP'
    else:
        prefix = 'EMP'
        
    last_user = CustomUser.objects.filter(emp_id__startswith=prefix).order_by('id').last()
    
    if last_user and last_user.emp_id:
        try:
            last_num = int(last_user.emp_id.replace(prefix, ""))
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
        
    return Response({"next_id": f"{prefix}{str(new_num).zfill(4)}"})


def get_managed_user_queryset(user, branch_code=None):
    if user.role == 'superadmin':
        return CustomUser.objects.all().order_by('id')
    if user.role == 'office_admin':
        # 🌟 Office Admin only sees central roles
        return CustomUser.objects.filter(role__in=CENTRAL_STAFF_ROLES).order_by('id')
    if user.role == 'admin':
        # 🌟 Branch Admin only sees Receptionists from their specific branch
        return CustomUser.objects.filter(role__in=BRANCH_STAFF_ROLES, branch=user.branch).order_by('id')
    return CustomUser.objects.none()


def get_allowed_target_roles(user):
    if user.role == 'superadmin':
        return SUPERADMIN_MANAGED_ROLES
    if user.role == 'office_admin':
        return CENTRAL_STAFF_ROLES  # 🌟 Excludes Receptionist
    if user.role == 'admin':
        return BRANCH_STAFF_ROLES   # 🌟 Restricts to Receptionist only
    return set()


def enforce_user_hierarchy(actor, payload, instance=None):
    data = payload.copy()
    target_role = str(data.get('role') or getattr(instance, 'role', 'receptionist')).strip()

    if target_role == 'superadmin':
        raise PermissionDenied("Super Admin accounts must be created through the seed file.")

    allowed_roles = get_allowed_target_roles(actor)
    if target_role not in allowed_roles:
        raise PermissionDenied(
            f"{actor.get_role_display()} cannot create or manage '{target_role}' accounts."
        )

    if instance and instance.role == 'superadmin':
        raise PermissionDenied("The seeded Super Admin account cannot be changed here.")

    if instance and actor.pk == instance.pk:
        if str(data.get('role') or instance.role) != instance.role:
            raise PermissionDenied("You cannot change your own role.")
        if data.get('is_active') is False:
            raise PermissionDenied("You cannot deactivate your own account.")

    if target_role == 'office_admin':
        data['branch'] = ALL_BRANCH_CODE
        return data

    if actor.role == 'office_admin':
        data['branch'] = ALL_BRANCH_CODE
    elif actor.role == 'admin':
        data['branch'] = actor.branch
    else:
        branch = str(data.get('branch') or getattr(instance, 'branch', '') or '').strip().upper()
        if branch not in BRANCH_CODES | {ALL_BRANCH_CODE}:
            raise ValidationError({'branch': 'Branch must be LNM, RYM, or ALL for this role.'})
        data['branch'] = branch

    if target_role == 'admin' and data['branch'] not in BRANCH_CODES:
        raise ValidationError({'branch': 'Branch Admin must belong to a single branch.'})

    if target_role in STAFF_ROLES and data['branch'] not in BRANCH_CODES | {ALL_BRANCH_CODE}:
        raise ValidationError({'branch': 'Staff accounts must belong to LNM, RYM, or ALL.'})

    return data

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class UserListCreateView(generics.ListCreateAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsBranchAdminOrSuperAdmin]

    def get_queryset(self):
        requested_branch = str(self.request.query_params.get('branch') or '').strip().upper()
        return get_managed_user_queryset(self.request.user, branch_code=requested_branch)

    def create(self, request, *args, **kwargs):
        sanitized_data = enforce_user_hierarchy(request.user, request.data)
        serializer = self.get_serializer(data=sanitized_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsBranchAdminOrSuperAdmin]

    def get_queryset(self):
        requested_branch = str(self.request.query_params.get('branch') or '').strip().upper()
        return get_managed_user_queryset(self.request.user, branch_code=requested_branch)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        sanitized_data = enforce_user_hierarchy(request.user, request.data, instance=instance)
        serializer = self.get_serializer(instance, data=sanitized_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.role == 'superadmin':
            raise PermissionDenied("The seeded Super Admin account cannot be deleted.")
        if instance.pk == request.user.pk:
            raise PermissionDenied("You cannot delete your own account.")
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class AdminResetPasswordView(generics.UpdateAPIView):
    serializer_class = AdminPasswordResetSerializer
    permission_classes = [IsBranchAdminOrSuperAdmin]

    def get_queryset(self):
        requested_branch = str(self.request.query_params.get('branch') or '').strip().upper()
        return get_managed_user_queryset(self.request.user, branch_code=requested_branch).exclude(role='superadmin')

    def update(self, request, *args, **kwargs):
        user_to_reset = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_to_reset.set_password(serializer.validated_data['new_password'])
        user_to_reset.save()
        
        return Response({"message": f"Password for {user_to_reset.username} reset successfully."}, 
                        status=status.HTTP_200_OK)
    
class RequestPasswordResetOTPView(APIView):
    permission_classes = [AllowAny] 

    def post(self, request):
        email = request.data.get('email')

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "This email is not registered in our system."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 1. Generate a random 6-digit OTP
        otp_code = str(random.randint(100000, 999999))

        # 2. Invalidate any old unused OTPs
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        # 3. Save the new OTP to the database
        PasswordResetOTP.objects.create(user=user, otp=otp_code)                    

        # 4. 🌟 THE FIX: Updated Email Text Formatting
        subject = "Sangi Hospital - Password Reset OTP"
        message = f"Hello {user.first_name or user.username},\n\nYour password reset code is: {otp_code}\n\nThis code will expire in 10 minutes.\nIf you did not request this, please ignore this email."
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            return Response(
                {"error": "Failed to send email. Check your Gmail configuration."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"message": "OTP has been sent successfully."}, 
            status=status.HTTP_200_OK
        )
    
class VerifyPasswordResetOTPView(APIView):
    permission_classes = [AllowAny] 

    def post(self, request):
        # 🌟 THE FIX: Directly extract data and strip spaces to prevent copy-paste errors
        email = request.data.get('email')
        otp_code = str(request.data.get('otp', '')).strip()
        new_password = request.data.get('new_password')

        if not email or not otp_code or not new_password:
            return Response({"error": "Please provide your email, OTP, and a new password."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Find the user
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response({"error": "Invalid request. Email not found."}, status=status.HTTP_400_BAD_REQUEST)
        except CustomUser.MultipleObjectsReturned:
            user = CustomUser.objects.filter(email=email).first()

        # 2. Find the active OTP for this user
        try:
            otp_record = PasswordResetOTP.objects.get(user=user, otp=otp_code, is_used=False)
        except PasswordResetOTP.DoesNotExist:
            return Response({"error": "Invalid or already used OTP. Please check the code and try again."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Check if the 10-minute timer expired
        if hasattr(otp_record, 'is_valid') and not otp_record.is_valid():
            return Response({"error": "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Success! Change the password and burn the OTP
        user.set_password(new_password)
        user.save()

        otp_record.is_used = True
        otp_record.save()

        return Response(
            {"message": "Password successfully reset. You can now log in with your new password."}, 
            status=status.HTTP_200_OK
        )


class SelfProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = SelfProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

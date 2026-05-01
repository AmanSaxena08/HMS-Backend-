from django.urls import path
from .views import CustomLoginView, UserListCreateView, UserDetailView, AdminResetPasswordView, RequestPasswordResetOTPView, VerifyPasswordResetOTPView, SelfProfileView
from .views import AdminResetPasswordView
from . import views

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='api_login'),
    path('me/', SelfProfileView.as_view(), name='self_profile'),
    path('manage/', UserListCreateView.as_view(), name='manage_users'),
    path('manage/<int:pk>/', UserDetailView.as_view(), name='manage_user_detail'),
    path('manage/<int:pk>/reset-password/', AdminResetPasswordView.as_view(), name='admin_reset_password'),
    path('request-reset-otp/', RequestPasswordResetOTPView.as_view(), name='request_otp'),
    path('verify-reset-otp/', VerifyPasswordResetOTPView.as_view(), name='verify_otp'), 
    path('next-emp-id/', views.get_next_emp_id, name='next_emp_id'),
]
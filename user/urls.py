from django.urls import path
from .views import *

urlpatterns = [
    path('register/', UserCreateView.as_view(), name="register"),
    path('login/', UserLoginView.as_view(), name='login'),
    path('send-reset-email/', PasswordResetEmailView.as_view(), name='send-reset-email'),
    path('verify-email/<uuid:uuid>/', VerifyEmailView.as_view(), name='verify_email'),
  
]
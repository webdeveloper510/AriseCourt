from django.urls import path
from .views import *

urlpatterns = [
    path('register/', UserCreateView.as_view(), name="register"),
    path('verify-email/<uuid:uuid>/', VerifyEmailView.as_view(), name='verify_email'),
]
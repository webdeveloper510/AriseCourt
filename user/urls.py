from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
from .views import LocationViewSet
from django.urls import include


router = DefaultRouter()
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'courts', CourtViewSet, basename='court')

urlpatterns = [
    path('register/', UserCreateView.as_view(), name="register"),
    path('login/', UserLoginView.as_view(), name='login'),
    path('send-reset-email/', PasswordResetEmailView.as_view(), name='send-reset-email'),
    path('verify-email/<uuid:uuid>/', VerifyEmailView.as_view(), name='verify_email'),
    path('reset-password/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('', include(router.urls)),
]

from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
from .views import LocationViewSet
from django.urls import include


router = DefaultRouter()
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'courts', CourtViewSet, basename='court')
router.register(r'create_admin', AdminViewSet, basename='create-Admin')
router.register(r'court-bookings', CourtBookingViewSet, basename='booking')
router.register(r'contact-us', ContactUsViewSet, basename='contactus')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', UserCreateView.as_view(), name="register"),
    path('login/', UserLoginView.as_view(), name='login'),
    path('send-reset-email/', PasswordResetEmailView.as_view(), name='send-reset-email'),
    path('verify-email/<uuid:uuid>/', VerifyEmailView.as_view(), name='verify_email'),
    path('reset-password/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('reporting-data/', StatsAPIView.as_view(), name='stats'),
    path('user-data/', UserData.as_view(), name='user-data'),
    path('profile/', ProfileView.as_view(), name='profile'),
]


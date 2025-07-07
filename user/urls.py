from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
from .views import LocationViewSet
from django.urls import include
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'get_locations_byAdmin', GetLocationViewSet, basename='get-location_byAdmin')
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
    path('check_court_availability/', CourtAvailabilityView.as_view(), name='check_court_availability'),
    path('stripe-webhook/', stripe_webhook, name='stripe-webhook'),
    path('create-checkout-session/', CreatePaymentIntentView.as_view(), name='create-checkout-session'),
    path('payment-success/', PaymentSuccessAPIView.as_view(), name='payment-success'),
    path('location_login/', LocationLoginView.as_view(), name='location_login'),
    path('my_location/', MyLocationView.as_view(), name='my-location'),
    path('users_my_locations/', UsersInMyLocationView.as_view(), name='users-in-my-location'),
    path('get_booking_byadmin/', AdminCourtBookingListView.as_view(), name='admin-location-users'),
    path('booked-locations/', BookedLocationDropdownView.as_view(), name='booked-locations-dropdown'),
    
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


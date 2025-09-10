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
router.register(r'all_locations', LocationListView, basename='all-locations')
router.register(r'get_courtbookings', CourtBookingWithoutTokenViewSet, basename='get-courtbookings')




urlpatterns = [
    path('', include(router.urls)),
    path('register/', UserCreateView.as_view(), name="register"),
    path('user-register/', UserRegisterView.as_view(), name="user_register"),
    path('delete-user/<int:user_id>/', UserDeleteView.as_view(), name="delete-user"),
    path('login/', UserLoginView.as_view(), name='login'),
    path('send-reset-email/', PasswordResetEmailView.as_view(), name='send-reset-email'),
    path('verify-email/<uuid:uuid>/', VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verify-email/<uuid:uuid>/', ResendVerificationView.as_view(), name='resend_verify_email'),
    path('reset-password/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('reporting-data/', StatsAPIView.as_view(), name='stats'),
    path('user-data/', UserData.as_view(), name='user-data'),
    
    path('users-data/', BookingListView.as_view(), name='users-data'),
    path('download_csv/', DownloadCSVView.as_view(), name='download-csv'),
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
    path('user_basic_data/', UserBasicDataView.as_view(), name='logged-in-user-data'),
    path('delete_pending_bookings/', DeletePendingBookingsAPIView.as_view(), name='delete-pending-bookings')
    
    
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


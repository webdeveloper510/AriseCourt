from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import *
from django.conf import settings
from .mail import MailUtils
from datetime import date
from django.db.models import Q
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from django.utils.timezone import now
import random
from rest_framework import viewsets, filters
from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_date
import stripe
from .utils import calculate_total_fee, calculate_duration
import json
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, time


# Create your views here.

stripe.api_key = settings.STRIPE_SECRET_KEY


class LargeResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10000
    

def get_tokens_for_user(user):
        refresh = RefreshToken.for_user(user)
        return {
            # 'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


class UserData(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        search_query = request.query_params.get('search', '')
        user_type = request.query_params.get('user_type')  

        # Initialize filters
        date_filter = Q()
        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                date_filter &= Q(created_at__date__range=(start, end))

        search_filter = Q()
        if search_query:
            search_filter |= Q(first_name__icontains=search_query)
            search_filter |= Q(last_name__icontains=search_query)
            search_filter |= Q(phone__icontains=search_query)
            search_filter |= Q(email__icontains=search_query)

        # Exclude SuperAdmin (0) and Admin (1)
        queryset = User.objects.exclude(user_type__in=[0, 1])
        queryset = queryset.filter(date_filter & search_filter)

        if user_type:
            try:
                queryset = queryset.filter(user_type=int(user_type))
            except ValueError:
                return Response({"message": "Invalid user_type"}, status=400)

        # ✅ Apply pagination manually
        paginator = LargeResultsSetPagination()
        paginated_qs = paginator.paginate_queryset(queryset, request)
        serialized_data = UserDataSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serialized_data.data)


class UserCreateView(APIView):
    def post(self, request):
        user = UserSerializer(data=request.data)
        if user.is_valid():
            data=user.save()
            MailUtils.send_verification_email(data)
            return Response({
                "message": "Please check your email to verify your account before logging in.",
                "status": status.HTTP_201_CREATED
            })
        return Response(user.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(request, username=email,password=password)
        if user is not None:
            if not user.is_verified:
                return Response({
                    'message': 'Email not verified. Please verify your email before logging in.',
                    'status_code': status.HTTP_403_FORBIDDEN
                }, status=status.HTTP_403_FORBIDDEN)
            token = get_tokens_for_user(user)
            user_data = UserLoginFieldsSerializer(user).data
            user_data['access_token'] = token['access']
            return Response({
                'code': '200',
                'message': 'Login Successfully',
                'data': user_data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'message': 'Incorrect Username and Password',
                'code': "400"
            }, status=status.HTTP_200_OK)
   
    
class VerifyEmailView(View):
    def get(self,request, uuid):
        user = get_object_or_404(User, uuid=uuid)
        
        if user.is_verified:
            return HttpResponse("Your email is already verified.")

        user.is_verified = True
        user.save()
        return HttpResponse("Email verified successfully! You can now log in.")


class PasswordResetEmailView(APIView):
    def post(self, request):
        serializer = PasswordResetEmailSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({'message': 'User with this email does not exist.','code': '400' }, status=status.HTTP_200_OK)

            otp = str(random.randint(100000, 999999))
            user.verified_otp = otp
            user.save()

            MailUtils.send_password_reset_email(user)

            return Response({'message': 'Password reset OTP sent to email.', 'code': '200'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found.", 'code':'400'}, status=status.HTTP_200_OK)

        if user.verified_otp != str(otp):
            return Response({"message": "Invalid OTP.", 'code': '400'}, status=status.HTTP_200_OK)

        return Response({"message": "OTP verified successfully.",'code': '200'}, status=status.HTTP_200_OK)
    

class ResendOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "Email is required.",'code': '400'}, status=status.HTTP_200_OK)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found.", 'code': '400'}, status=status.HTTP_200_OK)

        
        otp = str(random.randint(100000, 999999))
        user.verified_otp = otp
        user.save()

        # Reuse your existing email sending function
        MailUtils.send_password_reset_email(user)

        return Response({"message": "OTP and reset link have been resent to the email.", 'code': status.HTTP_200_OK}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "Validation failed.",
                "errors": serializer.errors
            }, status=status.HTTP_200_OK)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                "code": 400,
                "message": "User not found.",
            }, status=status.HTTP_200_OK)

        user.set_password(password)
        user.save()

        return Response({
            "code": 200,
            "message": "Password has been reset successfully.",
        }, status=status.HTTP_200_OK)


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__first_name', 'email', 'phone', 'city']
    
    def get_queryset(self):
        queryset = Location.objects.all()
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                queryset = queryset.filter(created_at__date__range=(start, end))
        return queryset
        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"message": "Location created successfully.","status_code": status.HTTP_201_CREATED,"data": serializer.data},status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({"message": "Location updated successfully.","status_code": status.HTTP_200_OK,"data": serializer.data},status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Location deleted successfully.","status_code": status.HTTP_200_OK},status=status.HTTP_200_OK)


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    pagination_class = LargeResultsSetPagination

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"message": "Court created successfully.","status_code": status.HTTP_201_CREATED,"data": serializer.data},status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({"message": "Court updated successfully.","status_code": status.HTTP_200_OK,"data": serializer.data},status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Court deleted successfully.","status_code": status.HTTP_200_OK},status=status.HTTP_200_OK)
    

class AdminViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = AdminRegistrationSerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name','last_name', 'email', 'phone']
    
    def get_queryset(self):
        queryset = User.objects.filter(user_type=1)
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                queryset = queryset.filter(created_at__date__range=[start, end])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_flag = request.data.get("access_flag", None)

        if access_flag is None:
            return Response({
                "message": "Missing Permission.",
                "status_code": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        self.perform_create(serializer)
        user = serializer.instance

        user.is_verified = True
        user.save()

        AdminPermission.objects.create(user=user, access_flag=str(access_flag))

        response_data = serializer.data
        response_data['access_flag'] = str(access_flag)

        return Response({
            "message": "Admin created successfully.",
            "status_code": status.HTTP_201_CREATED,
            "data": response_data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        password = request.data.get("password", None)
        if password:
            instance.set_password(password)
            instance.save()

        access_flag = request.data.get("access_flag", None)
        if access_flag is not None:
            try:
                admin_permission = AdminPermission.objects.get(user=instance)
                admin_permission.access_flag = str(access_flag)
                admin_permission.save()
            except AdminPermission.DoesNotExist:
                AdminPermission.objects.create(user=instance, access_flag=str(access_flag))

        return Response({
            "message": "Admin updated successfully.",
            "status_code": status.HTTP_200_OK,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Admin deleted successfully.","status_code": status.HTTP_200_OK}, status=status.HTTP_200_OK)
    

class CourtBookingViewSet(viewsets.ModelViewSet):
    queryset = CourtBooking.objects.all()
    serializer_class = CourtBookingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'user__phone']

    
    def list(self, request, *args, **kwargs):
        today = date.today()
        booking_type = request.query_params.get('type') 
        search = request.query_params.get('search')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # Filter bookings based on user
        if request.user.is_superuser:
            bookings = CourtBooking.objects.all()
        else:
            bookings = CourtBooking.objects.filter(user=request.user)

        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                bookings = bookings.filter(booking_date__range=(start, end))

        if search:
            bookings = bookings.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__phone__icontains=search) |
                Q(booking_date__icontains=search) 
            )

        # Return based on filter
        if booking_type == 'past':
            bookings = bookings.filter(booking_date__lt=today).order_by('-booking_date')
        else:
            bookings = bookings.filter(booking_date__gte=today).order_by('booking_date')

        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # If pagination is not applied (e.g., pagination class is not set)
        serializer = self.get_serializer(bookings, many=True)
        return Response({'bookings': serializer.data})
        # serializer = self.get_serializer(filtered_bookings, many=True)
        # return Response({'bookings': serializer.data})

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        start = data.get('start_time')
        end = data.get('end_time')

        try:
            start_time = datetime.strptime(start, "%H:%M:%S")
            end_time = datetime.strptime(end, "%H:%M:%S")

            if end_time <= start_time:
                return Response({"message": "End time must be after start time.", 'code': '400'}, status=status.HTTP_200_OK)

            duration = str(end_time - start_time)
            data['duration_time'] = duration  

        except:
            return Response({"message": "Invalid time format. Use HH:MM:SS", 'code': '400'}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        booking = serializer.save(user=request.user)
        MailUtils.booking_confirmation_mail(request.user,booking)
        return Response(serializer.data, status=201)
    
    
class ContactUsViewSet(viewsets.ModelViewSet):
    queryset = ContactUs.objects.all()
    serializer_class = ContactUsSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'message']

    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            self.perform_create(serializer)
            return Response({
                'code':'201',
                "message": "Thank you for contacting us!",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "code": "400",
            "message": "There was a problem with your submission.",
            "errors": serializer.errors
        }, status=status.HTTP_200_OK)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())  # Enables search

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "code": "200",
                "message": "Contact messages fetched successfully.",
                "data": serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "code": "200",
            "message": f"{queryset.count()} contact message(s) fetched successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    


class StatsAPIView(APIView):

    def get(self, request):
        total_users = User.objects.count()
        total_bookings = CourtBooking.objects.count()
        total_courts = Court.objects.count()
        total_profit = 0

        return Response({
            'total_users': total_users,
            'total_bookings': total_bookings,
            'total_courts': total_courts,
            'total_profit': total_profit
        })


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UpdateProfileSerializer(user, data=request.data, partial=True)  
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "code": "200",
            "message": "Profile updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

    def get(self, request):
        user = request.user
        serializer = UpdateProfileSerializer(user)
        return Response({
            "code": "200",
            "message": "Profile fetched successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)






class CourtAvailabilityView(APIView):
    def post(self, request, *args, **kwargs):
        location_id = request.data.get('location_id')
        booking_date = request.data.get('date')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')

        if not (location_id and booking_date):
            return Response({"error": "location_id and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Parse date and time
        try:
            date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
            if start_time and end_time:
                start_time_obj = time.fromisoformat(start_time)
                end_time_obj = time.fromisoformat(end_time)
            else:
                start_time_obj = None
                end_time_obj = None
        except ValueError:
            return Response({"error": "Invalid date or time format."}, status=status.HTTP_400_BAD_REQUEST)

        courts = Court.objects.filter(location_id=location_id)
        result = []

        for court in courts:
            bookings = CourtBooking.objects.filter(
                court=court,
                booking_date=date_obj,
                status__in=['pending', 'confirmed']
            )

            if start_time_obj and end_time_obj:
                bookings = bookings.filter(
                    start_time__lt=end_time_obj,
                    end_time__gt=start_time_obj
                )

            is_booked = bookings.exists()

            result.append({
                "court_id": court.id,
                "court_number": court.court_number,
                "is_booked": is_booked
            })

        return Response({
            "location_id": location_id,
            "date": booking_date,
            "courts": result
        }, status=status.HTTP_200_OK)
    







class CreatePaymentIntentView(APIView):
    def post(self, request):
        try:
            booking_id = request.data.get("booking_id")
            booking = CourtBooking.objects.get(id=booking_id)
            court = booking.court

            duration_hours = calculate_duration(booking.start_time, booking.end_time)
            fee_data = calculate_total_fee(court, duration_hours)
            total_amount = fee_data['total_amount']  # In cents

            intent = stripe.PaymentIntent.create(
                amount=int(total_amount),
                currency="usd",
                payment_method_types=["card"],
                metadata={
                    "booking_id": str(booking.id),
                    "court_id": str(court.id),
                }
            )

            # Save intent ID for reference
            booking.stripe_payment_intent_id = intent.id
            booking.save()

            return Response({
                "client_secret": intent.client_secret,
                "amount_details": {
                    "base_fee": fee_data["base_fee"],
                    "tax": fee_data["tax"],
                    "cc_fee": fee_data["cc_fee"],
                    "total": total_amount / 100
                }
            })

        except CourtBooking.DoesNotExist:
            return Response({"error": "Invalid booking ID"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)






@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        payment_intent_id = intent['id']
        amount_received = intent['amount_received'] / 100  # cents to dollars
        metadata = intent.get('metadata', {})
        booking_id = metadata.get('booking_id')
        customer_id = intent.get('customer')

        try:
            booking = CourtBooking.objects.get(id=booking_id)
            user = booking.user

            # Prevent duplicate payments if webhook is triggered multiple times
            payment, created = Payment.objects.get_or_create(
                stripe_payment_intent_id=payment_intent_id,
                defaults={
                    "user": user,
                    "booking": booking,
                    "amount": amount_received,
                    "payment_status": "successful",
                    "stripe_customer_id": customer_id,
                    "payment_date": now(),
                }
            )

            if booking.status != "confirmed":
                booking.status = "confirmed"
                booking.save()

        except CourtBooking.DoesNotExist:
            pass  # Optional: log this

    return HttpResponse(status=200)





class PaymentSuccessAPIView(APIView):
    def post(self, request):
        client_value = request.data.get("payment_intent_id")

        if not client_value:
            return Response({"error": "PaymentIntent ID is required"}, status=400)

        # Remove client_secret suffix if present
        payment_intent_id = client_value.split("_secret")[0]

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
            booking = payment.booking
            booking.status = 'confirmed'
            booking.save()

            return Response({"success": True})
        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)

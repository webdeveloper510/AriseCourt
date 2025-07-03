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
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            MailUtils.send_verification_email(user)
            return Response({
                "message": "Please check your email to verify your account before logging in.",
                "status": status.HTTP_201_CREATED
            }, status=status.HTTP_201_CREATED)

        # Extract the first field and its first error message
        first_field = next(iter(serializer.errors))
        first_error_message = serializer.errors[first_field][0]

        response_data = {
            "code": "400",
            "message": f"{first_field}: {first_error_message}"
        }

        return Response(response_data, status=status.HTTP_200_OK)

    

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
                    'code': "400",
                    'message': 'Email not verified. Please verify your email before logging in.'
                }, status=status.HTTP_200_OK)
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
    search_fields = ['user__first_name', 'email', 'phone', 'city','address_1','address_2','address_3','address_4','description','state','country']
    
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
        location_id = request.data.get("location_id")
        court_number = request.data.get("court_number")

        # Check if court with same number exists at the same location
        if Court.objects.filter(location_id=location_id, court_number=court_number).exists():
            return Response({
                "message": "Court with this number already exists at the same location.",
                "code": 400
            }, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Court created successfully.",
            "code": 200,
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        location_id = request.data.get("location_id", instance.location_id.id)
        court_number = request.data.get("court_number", instance.court_number)

        # Check for duplicates excluding current instance
        if Court.objects.filter(location_id=location_id, court_number=court_number).exclude(id=instance.id).exists():
            return Response({
                "message": "Another court with this number already exists at the same location.",
                "code": 400
            }, status=status.HTTP_200_OK)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Court updated successfully.",
            "code": 200,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Court deleted successfully.",
            "code": 200
        }, status=status.HTTP_200_OK)
    


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

        if booking_type == 'past':
            bookings = bookings.filter(booking_date__lt=today).order_by('-booking_date')
        else:
            bookings = bookings.filter(booking_date__gte=today).order_by('booking_date')

        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(bookings, many=True)
        return Response({'bookings': serializer.data})

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        court_id = data.get('court')
        booking_date = data.get('booking_date')
        start = data.get('start_time')
        end = data.get('end_time')

        try:
            start_time = datetime.strptime(start, "%H:%M:%S").time()
            end_time = datetime.strptime(end, "%H:%M:%S").time()

            if end_time <= start_time:
                return Response({"message": "End time must be after start time.", 'code': '400'}, status=status.HTTP_200_OK)

            duration = str(datetime.combine(date.min, end_time) - datetime.combine(date.min, start_time))
            data['duration_time'] = duration

        except:
            return Response({"message": "Invalid time format. Use HH:MM:SS", 'code': '400'}, status=status.HTTP_200_OK)

        # ✅ Block only if already booked with confirmed or paid
        if CourtBooking.objects.filter(
            court_id=court_id,
            booking_date=booking_date,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).filter(
            Q(status='confirmed') | Q(status='pending', booking_payments__payment_status='successful')
        ).exists():
            return Response({
                "message": "Court is already booked for the selected time.",
                "code": "409"
            }, status=status.HTTP_409_CONFLICT)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        # ✅ Admin or SuperAdmin books without payment
        if user.user_type in [0, 1]:  # SuperAdmin or Admin
            booking = serializer.save(
                user=user,
                payment_status='Paid',
                amount=0,
                status='confirmed'  # Mark confirmed so it blocks the court
            )
            MailUtils.booking_confirmation_mail(user, booking)
            return Response({
                "message": "Booking successful for admin (no payment needed).",
                "status_code": status.HTTP_201_CREATED,
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        # 🧾 Regular user booking
        booking = serializer.save(user=user)
        MailUtils.booking_confirmation_mail(user, booking)
        return Response(serializer.data, status=201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        data = request.data.copy()

        court_id = data.get('court', instance.court.id)
        booking_date = data.get('booking_date', instance.booking_date)
        start = data.get('start_time', instance.start_time.strftime("%H:%M:%S"))
        end = data.get('end_time', instance.end_time.strftime("%H:%M:%S"))

        try:
            start_time = datetime.strptime(start, "%H:%M:%S").time()
            end_time = datetime.strptime(end, "%H:%M:%S").time()

            if end_time <= start_time:
                return Response({"message": "End time must be after start time.", 'code': '400'}, status=status.HTTP_200_OK)

            duration = str(datetime.combine(date.min, end_time) - datetime.combine(date.min, start_time))
            data['duration_time'] = duration

        except:
            return Response({"message": "Invalid time format. Use HH:MM:SS", 'code': '400'}, status=status.HTTP_200_OK)

        # ✅ Exclude current booking when checking for conflict
        if CourtBooking.objects.filter(
            court_id=court_id,
            booking_date=booking_date,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).filter(
            Q(status='confirmed') | Q(status='pending', booking_payments__payment_status='successful')
        ).exclude(id=instance.id).exists():
            return Response({
                "message": "Court is already booked for the selected time.",
                "code": "409"
            }, status=status.HTTP_409_CONFLICT)

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Court booking updated successfully.",
            "status_code": status.HTTP_200_OK,
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()

        # ✅ Allow only SuperAdmin (0) or Admin (1)
        if request.user.user_type not in [0, 1]:
            return Response(
                {"message": "You do not have permission to delete this booking."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Optional: log or refund if needed here

        booking.delete()
        return Response(
            {"message": "Court booking deleted successfully.", "status_code": status.HTTP_200_OK},
            status=status.HTTP_200_OK
        )


    
    
    
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
            # Base query
            bookings = CourtBooking.objects.filter(
                court=court,
                status__in=['confirmed']
            )

            # Filter 1: Normal same-day bookings
            same_day_bookings = bookings.filter(booking_date=date_obj)

            # Filter 2: Repeating bookings (booked for 6 months)
            weekday = date_obj.weekday()  # Monday=0 ... Sunday=6
            six_months_back = date_obj - timedelta(weeks=26)

            repeating_bookings = bookings.filter(
                book_for_six_months=True,
                booking_date__lte=date_obj,
                booking_date__gte=six_months_back
            )

            repeating_bookings = [
                b for b in repeating_bookings
                if b.booking_date.weekday() == weekday
            ]

            # Combine all bookings to check time conflict
            combined_bookings = list(same_day_bookings) + list(repeating_bookings)

            is_booked = False
            if start_time_obj and end_time_obj:
                for booking in combined_bookings:
                    if booking.start_time < end_time_obj and booking.end_time > start_time_obj:
                        is_booked = True
                        break
            else:
                is_booked = bool(combined_bookings)

            result.append({
                "court_id": court.id,
                "court_number": court.court_number,
                "court_fee_hrs": court.court_fee_hrs,  
                "start_time": court.start_time, 
                "end_time": court.end_time, 
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
            total_price = booking.total_price
            tax = court.tax                   
            cc_fees = court.cc_fees 
            fee_data = calculate_total_fee(total_price, tax, cc_fees)
            total_amount = fee_data['total_amount']
            total_price = int(total_amount * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=total_price,
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
                    "total": total_price
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
        payment_intent = request.data.get("payment_intent_id")
        print("payment_intent",payment_intent)
        if not payment_intent:
            return Response({"error": "PaymentIntent ID is required"}, status=400)

        # Remove _secret part from PaymentIntent if present
        payment_intent_id = payment_intent.split("_secret")[0]


        print("hascjkhklhjackljhk",payment_intent_id)

        try:
            # Get the payment using the payment intent ID
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)

            # Get the related booking
            booking = payment.booking

            # ✅ Mark booking as confirmed (not completed)
            booking.status = 'confirmed'
            booking.save()

            # ✅ Update correct field: payment_status
            payment.payment_status = 'successful'
            payment.save()

            return Response({"success": True})

        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        
        
class LocationLoginView(APIView):
    def post(self, request):
        email     = request.data.get("email")
        password  = request.data.get("password")
        court_id  = request.data.get("court_id")

        # Get location
        try:
            location = Location.objects.get(email=email)
        except Location.DoesNotExist:
            return Response({"error": "Invalid email"}, status=400)

        # Check password
        if location.password != password:
            return Response({"error": "Incorrect password"}, status=401)

        # Get court
        try:
            court = Court.objects.get(id=court_id, location_id=location)
        except Court.DoesNotExist:
            return Response({"error": "Invalid court"}, status=400)

        # Default court time if not set
        start_time = court.start_time or time(9, 0)
        end_time = court.end_time or time(21, 0)

        # Round current time to next hour
        now = datetime.now()
        if now.minute > 0:
            now = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            now = now.replace(minute=0, second=0, microsecond=0)
 
        today = date.today()
        bookings = CourtBooking.objects.filter(court=court, booking_date=today)

        slots = []
        for i in range(4):
            slot_start = now + timedelta(hours=i)
            slot_end = slot_start + timedelta(hours=1)

            # Don't show slots after court end time
            if slot_end.time() > end_time:
                break

            # Check if this slot is booked
            booked = None
            for b in bookings:
                b_start = datetime.combine(today, b.start_time)
                b_end = datetime.combine(today, b.end_time)
                if b_start <= slot_start < b_end:
                    booked = b
                    break

            if booked:
                slots.append({
                    "code": i + 1,
                    "court_id": court.id,
                    "status": "BOOKED",
                    "user_name": booked.user.first_name,
                    "start_time": booked.start_time.strftime("%H:%M"),
                    "end_time": booked.end_time.strftime("%H:%M")
                })
            else:
                slots.append({
                    "code": i + 1,
                    "court_id": court.id,
                    "status": "OPEN",
                    "start_time": slot_start.strftime("%H:%M"),
                    "end_time": slot_end.strftime("%H:%M")
                })

        return Response({"slots": slots}, status=200)
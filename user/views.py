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
from django.contrib.auth.hashers import check_password
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F, FloatField
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
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
import openpyxl
from io import BytesIO

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
        user = request.user

        # Get optional query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        search_query = request.query_params.get('search', '')
        user_type = request.query_params.get('user_type')
        address_text = request.query_params.get('location', '').strip()  #  Full address text

        # Base queryset: Exclude SuperAdmin (0) and Admin (1), only users with bookings
        queryset = User.objects.exclude(user_type__in=[0, 1]).filter(court_bookings__isnull=False)

        #  Search by user fields
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        #  Filter by user_type
        if user_type:
            try:
                queryset = queryset.filter(user_type=int(user_type))
            except ValueError:
                return Response({"message": "Invalid user_type"}, status=400)

        #  Address Filter (Admin: limited to assigned locations)
        address_filter = Q()
        if address_text:
            address_filter &= (
                Q(court_bookings__court__location_id__address_1__icontains=address_text) |
                Q(court_bookings__court__location_id__address_2__icontains=address_text) |
                Q(court_bookings__court__location_id__address_3__icontains=address_text) |
                Q(court_bookings__court__location_id__address_4__icontains=address_text)
            )

        # Admin restriction (can only see assigned locations)
        if user.user_type == 1:
            assigned_location_ids = user.locations.values_list('id', flat=True)
            address_filter &= Q(court_bookings__court__location_id__in=assigned_location_ids)

        if address_filter:
            queryset = queryset.filter(address_filter).distinct()

        # Date filter on booking creation date
        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                queryset = queryset.filter(
                    court_bookings__created_at__date__range=(start, end)
                ).distinct()
            else:
                return Response({"message": "Invalid date format"}, status=400)

        #  Paginate and return
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
    

class UserDeleteView(APIView):
    def delete(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.delete()
        return Response({
            "message": "User deleted successfully.",
            "status": status.HTTP_200_OK
        }, status=status.HTTP_200_OK)

    

# class UserLoginView(APIView):
#     def post(self, request):
#         serializer = UserLoginSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         email = serializer.validated_data['email']
#         password = serializer.validated_data['password']
#         location_id = serializer.validated_data.get('location')

#         user = authenticate(request, username=email, password=password)

#         if user is not None:
#             #  Location logic for Admins (user_type == 1)
#             if user.user_type == 1:
#                 if location_id:  # Location was passed by admin
#                     if not user.location or str(user.location.id) != str(location_id):
#                         return Response({
#                             'message': 'You are not assigned to this location. First please register for this location.',
#                             'code': 400
#                         }, status=status.HTTP_200_OK)

#             #  Location logic for other users (user_type > 1)
#             elif user.user_type > 1:
#                 if not location_id:
#                     return Response({
#                         'message': 'Location is required.',
#                         'code': 400
#                     }, status=status.HTTP_200_OK)

#                 if not user.location or str(user.location.id) != str(location_id):
#                     return Response({
#                         'message': 'You are not assigned to this location. First please register for this location.',
#                         'code': 400
#                     }, status=status.HTTP_200_OK)

#             # Email verification check
#             if not user.is_verified:
#                 return Response({
#                     'message': 'Email not verified. Please verify your email before logging in.',
#                     'status_code': status.HTTP_403_FORBIDDEN
#                 }, status=status.HTTP_403_FORBIDDEN)

#             #  Generate token and return user data
#             token = get_tokens_for_user(user)
#             user_data = UserLoginFieldsSerializer(user).data
#             user_data['access_token'] = token['access']

#             return Response({
#                 'code': '200',
#                 'message': 'Login Successfully',
#                 'data': user_data
#             }, status=status.HTTP_200_OK)

#         #  Invalid credentials
#         return Response({
#             'message': 'Incorrect Username or Password',
#             'code': "400"
#         }, status=status.HTTP_200_OK)


class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']
        location_id = serializer.validated_data.get('location')  # Optional

        user = authenticate(request, username=email, password=password)

        if user is None:
            return Response({
                'message': 'User details are incorrect or location is not assigned',
                'code': "400"
            }, status=status.HTTP_200_OK)

        if not user.is_verified:
            return Response({
                'message': 'Email not verified. Please verify your email before logging in.',
                'code': 400
            }, status=status.HTTP_200_OK)

        # SuperAdmin (user_type == 0) logic
        if user.user_type == 0:
            if location_id:
                location, _ = Location.objects.get_or_create(
                    id=location_id,
                    defaults={'name': f'Location {location_id}'}
                ) 
                if not user.locations.filter(id=location_id).exists():
                    user.locations.add(location)

        # Admin (user_type == 1) logic — location is now required
        elif user.user_type == 1:
            if not location_id:
                return Response({
                    'message': 'Incorrect login details or you are not assigned to this location..',
                    'code': 400
                }, status=status.HTTP_200_OK)

            if not user.locations.filter(id=location_id).exists():
                return Response({
                    'message': 'Incorrect login details or you are not assigned to this location..',
                    'code': 400
                }, status=status.HTTP_200_OK)

        # All others (Coach, Player, Court) must have assigned location
        else:
            if not location_id:
                return Response({
                    'message': 'Location is required.',
                    'code': 400
                }, status=status.HTTP_200_OK)

            if not user.locations.filter(id=location_id).exists():
                return Response({
                    'message': 'User details are incorrect or location is not assigned',
                    'code': 400
                }, status=status.HTTP_200_OK)

        # Generate tokens
        token = get_tokens_for_user(user)
        user_data = UserLoginFieldsSerializer(user).data
        user_data['access_token'] = token['access']

        return Response({
            'code': '200',
            'message': 'Login Successfully',
            'data': user_data
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
        email = request.data.get('email').strip().lower()
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
        email = request.data.get('email').strip().lower()

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
    # queryset = Location.objects.all()
    queryset = Location.objects.filter(status=False)  # Only unassigned locations

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
        return Response({
            "message": "Location created successfully.",
            "status_code": status.HTTP_201_CREATED,
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_name = request.data.get('name')

        if new_name:
            name_locations = Location.objects.filter(name__iexact=new_name)
            for loc in name_locations:
                if loc.id != instance.id:
                    return Response({
                        "message": "Location with this name already exists.",
                        "status_code": 400
                    }, status=200)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Location updated Successfully.",
            "status_code": 200,
            "data": serializer.data
        }, status=200)

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
            }, status=status.HTTP_400_BAD_REQUEST)

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
    

###############################################   ADMIN   ###############################################

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
        location_id = request.data.get("location_id")

        #  Use correct M2M lookup
        # if location_id:
        #     existing_admin = User.objects.filter(
        #         user_type=1,
        #         locations__id=location_id
        #     ).exists()

        #     if existing_admin:
        #         location = Location.objects.filter(id=location_id, status=True).first()
        #         if location:
        #             return Response({
        #                 "message": "This location is already assigned to another admin.",
        #                 "code": 400
        #             }, status=status.HTTP_200_OK)

        access_flag = request.data.get("access_flag", None)

        if access_flag is None:
            return Response({
                "message": "Missing Permission.",
                "status_code": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        self.perform_create(serializer)
        user = serializer.instance

        #  Make user verified
        user.is_verified = True
        user.save()

        #  Update location status if assigned
        if user.locations.exists():
            # Location.objects.filter(id__in=user.locations.values_list('id', flat=True)).update(status=True)
            Location.objects.filter(id__in=user.locations.values_list('id', flat=True))


        # Set access flag
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

        location_id = request.data.get("location_id")
        access_flag = request.data.get("access_flag")
        password = request.data.get("password")
        country = request.data.get("country")

        location_obj = None

        # Validate and fetch location if provided
        if location_id:
            try:
                location_id = int(location_id)
                location_obj = get_object_or_404(Location, id=location_id)
            except (ValueError, TypeError):
                return Response({
                    "message": "Invalid location ID.",
                    "code": 400
                }, status=status.HTTP_200_OK)

            # Check if location already assigned to another admin
            is_conflict = User.objects.filter(
                user_type=1,
                locations__id=location_id
            ).exclude(id=instance.id).exists()

            if is_conflict and location_obj.status:
                return Response({
                    "message": "This location is already assigned to another admin.",
                    "code": 400
                }, status=status.HTTP_200_OK)

        # Update other fields via serializer (except location)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Password update
        if password:
            instance.set_password(password)
            instance.save()

        # Assign location if valid
        if location_obj:
            # Deactivate old locations
            instance.locations.exclude(id=location_obj.id).update(status=False)

            # Clear and assign new one
            instance.locations.set([location_obj])

            # Activate the new location
            location_obj.status = True
            location_obj.save()

        #  Update or create admin permission
        if access_flag is not None:
            AdminPermission.objects.update_or_create(
                user=instance,
                defaults={"access_flag": str(access_flag)}
            )

         #  Update country if provided
        target_location = location_obj or instance.locations.first()
        if country and target_location:
            target_location.country = country
            target_location.save()

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
    search_fields = ['user__first_name','user__last_name','user__email','user__phone','court__location_id__name','court__location_id__city','court__location_id__state','court__location_id__country','court__location_id__description','court__location_id__address_1','court__location_id__address_2','court__location_id__address_3','court__location_id__address_4']

    def list(self, request, *args, **kwargs):
        today = date.today()
        booking_type = request.query_params.get('type') 
        search = request.query_params.get('search')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        location_address = request.query_params.get('location')

        # Get bookings based on user type
        if request.user.is_superuser:
            bookings = CourtBooking.objects.filter(
                status='confirmed'
            )
        else:
            bookings = CourtBooking.objects.filter(
                user=request.user,
                status='confirmed'
            )


        # Annotate a combined address field
        bookings = bookings.annotate(
            full_address=Concat(
                'court__location_id__address_1', Value(' '),
                'court__location_id__address_2', Value(' '),
                'court__location_id__address_3', Value(' '),
                'court__location_id__address_4', output_field=CharField()
            )
        )

        
        bookings = bookings.annotate(
            location_address=Concat(
                'court__location_id__address_1', Value(' '),
                'court__location_id__address_2', Value(' '),
                'court__location_id__address_3', Value(' '),
                'court__location_id__address_4', Value(' '),
                'court__location_id__name',
                output_field=CharField()
            )
        )

        if location_address:
            bookings = bookings.filter(
                location_address__icontains=location_address.strip()
            )

        # Filter by date range
        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                bookings = bookings.filter(booking_date__range=(start, end))

        # Filter by search
        if search:
            bookings = bookings.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__phone__icontains=search) |
                Q(booking_date__icontains=search) |
                Q(court__location_id__name__icontains=search) |
                Q(court__location_id__city__icontains=search) |
                Q(court__location_id__state__icontains=search) |
                Q(court__location_id__country__icontains=search) |
                Q(court__location_id__description__icontains=search) |
                Q(full_address__icontains=search)  #  Search in combined address
            )
 
        # Filter by booking type (past/upcoming)
        if booking_type == 'past':
            bookings = bookings.filter(booking_date__lt=today).order_by('-booking_date')
        else:
            bookings = bookings.filter(booking_date__gte=today).order_by('booking_date')

        # Paginate and return response
        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(bookings, many=True)
        return Response({'bookings': serializer.data})

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        court_id = data.get('court') or data.get('court_id')
        booking_date = data.get('booking_date')
        start = data.get('start_time')
        end = data.get('end_time')
        book_for_four_weeks = data.get('book_for_four_weeks') in [True, 'true', 'True', 1, '1']

        try:
            start_time = datetime.strptime(start, "%H:%M:%S").time()
            end_time = datetime.strptime(end, "%H:%M:%S").time()

            if end_time <= start_time:
                return Response({"message": "End time must be after start time.", 'code': '400'}, status=status.HTTP_200_OK)

            duration_timedelta = datetime.combine(date.min, end_time) - datetime.combine(date.min, start_time)
            duration = str(duration_timedelta)
            data['duration_time'] = duration

        except:
            return Response({"message": "Invalid time format. Use HH:MM:SS", 'code': '400'}, status=status.HTTP_200_OK)

        if CourtBooking.objects.filter(
            court_id=court_id,
            booking_date=booking_date,
            start_time__lt=start_time,
            end_time__gt=end_time
        ).filter(
            Q(status='confirmed') | Q(status='pending', booking_payments__payment_status='successful')
        ).exists():
            return Response({
                "message": "Court is already booked for the selected time.",
                "code": "400"
            }, status=status.HTTP_409_CONFLICT)

        #  Calculate on_amount (total + tax + cc_fees)
        try:
            on_amount = float(data.get('on_amount') or 0)
            court = Court.objects.get(id=court_id)
            tax_percent = float(court.tax or 0)
            cc_fees_percent = float(court.cc_fees or 0)
            tax_amount = on_amount * (tax_percent / 100)
            cc_fee_amount = on_amount * (cc_fees_percent / 100)
            total = on_amount + tax_amount + cc_fee_amount
            # data['on_amount'] = str(total)  #  Save to DB
            data['on_amount'] = "{:.2f}".format(total)  # force 2 decimal places
            data['total'] = total
        except:
            return Response({"message": "Failed to calculate on_amount", 'code': '400'}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        created_bookings = []

        if user.user_type in [0, 1]:
            main_booking = serializer.save(user=user, status='confirmed')
        else:
            main_booking = serializer.save(user=user)

        MailUtils.booking_confirmation_mail(user, main_booking)
        created_bookings.append(main_booking)

        #  Repeat for next 3 weeks (if book_for_four_weeks is true)
        if book_for_four_weeks:
            original_date = datetime.strptime(booking_date, "%Y-%m-%d").date()
            for i in range(1, 4):
                next_date = original_date + timedelta(weeks=i)

                if not CourtBooking.objects.filter(
                    court_id=court_id,
                    booking_date=next_date,
                    start_time__lt=start_time,
                    end_time__gt=end_time
                ).filter(
                    Q(status='confirmed') | Q(status='pending', booking_payments__payment_status='successful')
                ).exists():
                    new_booking = CourtBooking.objects.create(
                        user=user,
                        court_id=court_id,
                        booking_date=next_date,
                        start_time=start_time,
                        end_time=end_time,
                        duration_time=duration,
                        book_for_four_weeks=True,
                        on_amount=str(total),
                        total_price=data.get('total_price'),
                        parent_booking=str(main_booking.id),  # Save main booking ID here
                        status=main_booking.status
                    )
                    created_bookings.append(new_booking)
        
        response_serializer = self.get_serializer(created_bookings, many=True)
        return Response({
            "message": "Bookings created successfully.",
            "status_code": status.HTTP_201_CREATED,
            "data": response_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            "message": "Booking updated successfully.",
            "status_code": status.HTTP_200_OK,
            "data": serializer.data
        }, status=status.HTTP_200_OK)


    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()

        # Allow only SuperAdmin (0) or Admin (1)
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        allowed_roles = [2, 3, 4]  # Coach, Player, Court

        if user.user_type == 1:  # Admin
            assigned_location_ids = user.locations.values_list('id', flat=True)

            total_users = User.objects.filter(
            user_type__in=allowed_roles,
            locations__id__in=assigned_location_ids  # Link through M2M relationship
            ).distinct().count()

            total_bookings = CourtBooking.objects.filter(
                court__location_id__in=assigned_location_ids
            ).count()

            total_courts = Court.objects.filter(
                location_id__in=assigned_location_ids
            ).count()

            booking_on_amounts = CourtBooking.objects.filter(
                court__location_id__in=assigned_location_ids
            ).values_list('on_amount', flat=True)

            # booking_on_amounts = CourtBooking.objects.filter(
            #     court__location_id__in=assigned_location_ids,
            #     status='confirmed',
            #     booking_payments__payment_status='successful'
            # ).values_list('on_amount', flat=True)

        else:  # SuperAdmin
            total_users = User.objects.filter(user_type__in=allowed_roles).count()
            total_bookings = CourtBooking.objects.count()
            total_courts = Court.objects.count()

            booking_on_amounts = CourtBooking.objects.values_list('on_amount', flat=True)

            # booking_on_amounts = CourtBooking.objects.filter(
            #     status='confirmed',
            #     booking_payments__payment_status='successful'
            # ).values_list('on_amount', flat=True)

        #  Safely convert on_amounts to float, ignoring bad data
        def safe_float(val):
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0

        total_profit = sum(safe_float(x) for x in booking_on_amounts)

        return Response({
            'total_users': total_users,
            'total_bookings': total_bookings,
            'total_courts': total_courts,
            'total_profit': f"${total_profit:.2f}"
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



# from user.utils import register_smtp_for_user
# class ProfileView(APIView):
#     permission_classes = [IsAuthenticated]

#     def put(self, request):
#         user = request.user

#         # Check if SMTP is being updated
#         is_updating_smtp = request.data.get("EMAIL_HOST_USER") or request.data.get("EMAIL_HOST_PASSWORD")

#         if is_updating_smtp:
#             smtp_config = {
#                 "EMAIL_HOST_USER": request.data.get("EMAIL_HOST_USER"),
#                 "EMAIL_HOST_PASSWORD": request.data.get("EMAIL_HOST_PASSWORD"),
#                 "EMAIL_HOST": request.data.get("EMAIL_HOST"),  # optional
#                 "EMAIL_PORT": request.data.get("EMAIL_PORT"),  # optional
#                 "EMAIL_USE_TLS": request.data.get("EMAIL_USE_TLS", True),
#             }

#             smtp_check = register_smtp_for_user(user, smtp_config)
#             if not smtp_check["success"]:
#                 return Response({
#                     "code": "400",
#                     "message": smtp_check["message"],
#                 }, status=status.HTTP_400_BAD_REQUEST)

#         # Now continue to update the rest of the profile fields
#         serializer = UpdateProfileSerializer(user, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()

#         return Response({
#             "code": "200",
#             "message": "Profile updated successfully",
#             "data": serializer.data
#         }, status=status.HTTP_200_OK)




# class CourtAvailabilityView(APIView):

#     def post(self, request, *args, **kwargs):
#         location_id = request.data.get('location_id')
#         booking_date = request.data.get('date')
#         start_time = request.data.get('start_time')
#         end_time = request.data.get('end_time')

#         if not (location_id and booking_date):
#             return Response({"error": "location_id and date are required."}, status=status.HTTP_400_BAD_REQUEST)

#         # Parse date and time
#         try:
#             date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
#             if start_time and end_time:
#                 start_time_obj = time.fromisoformat(start_time)
#                 end_time_obj = time.fromisoformat(end_time)
#             else:
#                 start_time_obj = None
#                 end_time_obj = None
#         except ValueError:
#             return Response({"error": "Invalid date or time format."}, status=status.HTTP_400_BAD_REQUEST)

#         courts = Court.objects.filter(location_id=location_id)
#         result = []

#         for court in courts:
#             # FIXED: Fetch bookings from ALL users, not just current user
#             bookings = CourtBooking.objects.filter(
#                 court=court,
#                 status__in=['pending', 'confirmed']
#             )

#             # Filter 1: Normal same-day bookings
#             same_day_bookings = bookings.filter(booking_date=date_obj)

#             # Filter 2: Repeating bookings (booked for 6 months)
#             weekday = date_obj.weekday()  # Monday=0 ... Sunday=6
#             six_months_back = date_obj - timedelta(weeks=26)

#             repeating_bookings = bookings.filter(
#                 book_for_four_weeks=True,
#                 booking_date__lte=date_obj,
#                 booking_date__gte=six_months_back
#             )

#             repeating_bookings = [
#                 b for b in repeating_bookings
#                 if b.booking_date.weekday() == weekday
#             ]

#             # Combine all bookings to check time conflict
#             combined_bookings = list(same_day_bookings) + list(repeating_bookings)

#             is_booked = False
#             if start_time_obj and end_time_obj:
#                 for booking in combined_bookings:
#                     if booking.start_time < end_time_obj and booking.end_time > start_time_obj:
#                         # Optional debug
#                         # print(f"Conflict with booking by user {booking.user_id}: {booking.start_time}-{booking.end_time}")
#                         is_booked = True
#                         break
#             else:
#                 is_booked = bool(combined_bookings)

#             result.append({
#                 "court_id": court.id,
#                 "court_number": court.court_number,
#                 "court_fee_hrs": court.court_fee_hrs,  
#                 "start_time": court.start_time, 
#                 "end_time": court.end_time, 
#                 "is_booked": is_booked
#             })

#         return Response({
#             "location_id": location_id,
#             "date": booking_date,
#             "courts": result
#         }, status=status.HTTP_200_OK)

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
            is_booked = False

            # Condition 1: Requested time falls within CLOSED court hours
            if start_time_obj and end_time_obj:
                if court.start_time and court.end_time:
                    if start_time_obj < court.end_time and end_time_obj > court.start_time:
                        is_booked = True

            #  Condition 2: Check for regular and repeating bookings
            bookings = CourtBooking.objects.filter(
                court=court,
                status__in=['confirmed']
            )
            same_day_bookings = bookings.filter(booking_date=date_obj)

            weekday = date_obj.weekday()
            six_months_back = date_obj - timedelta(weeks=26)

            repeating_bookings = bookings.filter(
                book_for_four_weeks=True,
                booking_date__lte=date_obj,
                booking_date__gte=six_months_back
            )
            repeating_bookings = [
                b for b in repeating_bookings if b.booking_date.weekday() == weekday
            ]

            combined_bookings = list(same_day_bookings) + list(repeating_bookings)

            if start_time_obj and end_time_obj and not is_booked:
                for booking in combined_bookings:
                    if booking.start_time < end_time_obj and booking.end_time > start_time_obj:
                        is_booked = True
                        break
            elif not start_time_obj or not end_time_obj:
                is_booked = bool(combined_bookings)

            result.append({
                "court_id": court.id,
                "court_number": court.court_number,
                "court_fee_hrs": court.court_fee_hrs,
                "start_time": court.start_time,  # closed start
                "end_time": court.end_time,      # closed end
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

            #  Create Checkout Session (for redirect URL)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Court Booking #{booking.id}",
                            },
                            "unit_amount": total_price,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                metadata={
                    "booking_id": str(booking.id),
                    "court_id": str(court.id),
                },
                success_url=f"http://localhost:3000/payment/success?payment_intent_id={intent.id}",
                # success_url="http://localhost:3000/payment/success?payment_intent_id={intent.id}",
                cancel_url="https://yourdomain.com/cancel",
            )


            # Save intent ID for reference
            booking.stripe_payment_intent_id = intent.id
            booking.save()

            return Response({
                "client_secret": intent.client_secret,
                "checkout_url": session.url,
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
        if not payment_intent:
            return Response({"error": "PaymentIntent ID is required"}, status=400)

        # Remove _secret part from PaymentIntent if present
        payment_intent_id = payment_intent.split("_secret")[0]

        try:
            # Get the payment using the payment intent ID
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)

            # Get the related booking
            booking = payment.booking


            #  Mark this booking as confirmed
            booking.status = 'confirmed'
            booking.save()

            #  Update payment status
            payment.payment_status = 'successful'
            payment.save()

            #  Update other bookings for the same court with book_for_four_weeks=True and status='pending'
            CourtBooking.objects.filter(
                parent_booking=str(booking.id),
                status='pending'
            ).update(status='confirmed')

            return Response({"success": True})

        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
    
    # def post(self, request):
    #     payment_intent = request.data.get("payment_intent_id")
    #     if not payment_intent:
    #         return Response({"error": "PaymentIntent ID is required"}, status=400)

    #     # Remove _secret part from PaymentIntent if present
    #     payment_intent_id = payment_intent.split("_secret")[0]


    #     try:
    #         # Get the payment using the payment intent ID
    #         payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)

    #         # Get the related booking
    #         booking = payment.booking

    #         # Mark booking as confirmed (not completed)
    #         booking.status = 'confirmed'
    #         booking.save()

    #         #  Update correct field: payment_status
    #         payment.payment_status = 'successful'
    #         payment.save()

    #         return Response({"success": True})

    #     except Payment.DoesNotExist:
    #         return Response({"error": "Payment not found"}, status=404)



  
# class LocationLoginView(APIView):
    # def post(self, request):
    #     email        = request.data.get("email")
    #     password     = request.data.get("password")
    #     court_id     = request.data.get("court_id")
    #     location_id  = request.data.get("location_id")

    #     if not (email and password and location_id):
    #         return Response({"message": "Email, password, and location_id are required.", "code": 400}, status=200)

    #     # Get user by email and location
    #     try:
    #         user = User.objects.get(email=email, locations__id=location_id)
    #     except User.DoesNotExist:
    #         return Response({"message": "Invalid email or location.", "code": 400}, status=200)

    #     # Check password
    #     if not check_password(password, user.password):
    #         return Response({"message": "Incorrect password.", "code": 400}, status=200)

    #     # Get court belonging to location
    #     try:
    #         court = Court.objects.get(id=court_id, location_id=location_id)
    #     except Court.DoesNotExist:
    #         return Response({"message": "Invalid court for this location.", "code": 400}, status=200)

    #     # Set time slots logic
    #     start_time = court.start_time or time(9, 0)
    #     end_time = court.end_time or time(21, 0)

    #     now = datetime.now()
    #     if now.minute > 0:
    #         now = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    #     else:
    #         now = now.replace(minute=0, second=0, microsecond=0)

    #     today = date.today()
    #     bookings = CourtBooking.objects.filter(court=court, booking_date=today)

    #     slots = []
    #     for i in range(4):
    #         slot_start = now + timedelta(hours=i)
    #         slot_end = slot_start + timedelta(hours=1)

    #         if slot_end.time() > end_time:
    #             break

    #         booked = None
    #         for b in bookings:
    #             b_start = datetime.combine(today, b.start_time)
    #             b_end = datetime.combine(today, b.end_time)
    #             if b_start <= slot_start < b_end:
    #                 booked = b
    #                 break

    #         if booked:
    #             slots.append({
    #                 "code": i + 1,
    #                 "court_id": court.id,
    #                 "location_id": court.location_id.id,
    #                 "court_number":court.court_number,
    #                 "booking_date":bookings.booking_date,
    #                 "status": "BOOKED",
    #                 "user_name": booked.user.first_name,
    #                 "start_time": booked.start_time.strftime("%H:%M"),
    #                 "end_time": booked.end_time.strftime("%H:%M")
    #             })
    #         else:
    #             slots.append({
    #                 "code": i + 1,
    #                 "court_id": court.id,
    #                 "location_id": court.location_id.id,
    #                 "status": "OPEN",
    #                 "start_time": slot_start.strftime("%H:%M"),
    #                 "end_time": slot_end.strftime("%H:%M")
    #             })

    #     return Response({"slots": slots, "location_id": court.location_id.id}, status=200)




class LocationLoginView(APIView):

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password")
        location_id = request.data.get("location_id")
        court_id = request.data.get("court_id")

        # Validate required fields
        if not (email and password and location_id and court_id):
            return Response({
                "message": "Email, password, location_id, and court_id are required.",
                "code": 400
            }, status=200)

        try:
            location_id = int(location_id)
        except (TypeError, ValueError):
            return Response({
                "message": "Invalid location_id format.",
                "code": 400
            }, status=200)

        try:
            court_id = int(court_id)
        except (TypeError, ValueError):
            return Response({
                "message": "Invalid court_id format.",
                "code": 400
            }, status=200)

        #  Use current time
        now = datetime.now()

        try:
            user = User.objects.get(email__iexact=email, locations__id=location_id)
        except User.DoesNotExist:
            return Response({
                "message": "Invalid email or location.",
                "code": 400
            }, status=200)

        if not check_password(password, user.password):
            return Response({
                "message": "Incorrect password.",
                "code": 400
            }, status=200)

        try:
            court = Court.objects.get(id=court_id, location_id=location_id)
        except Court.DoesNotExist:
            return Response({
                "message": "Invalid court for this location.",
                "code": 400
            }, status=200)

        #  Fetch bookings for current date only
        bookings = CourtBooking.objects.filter(
            court=court,
            booking_date=now.date()
        ).order_by("start_time")

        slots = []
        added_booking_ids = set()

        for booked in bookings:
            booking_start = datetime.combine(booked.booking_date, booked.start_time)
            if booking_start < now:
                continue  # Skip past bookings for today

            if booked.id in added_booking_ids:
                continue

            slots.append({
                "code": len(slots) + 1,
                "court_id": court.id,
                "location_id": court.location_id.id,
                "court_number": court.court_number,
                "booking_date": booked.booking_date.strftime("%Y-%m-%d"),
                "status": "BOOKED",
                "user_name": f"{booked.user.first_name} {booked.user.last_name}".strip(),
                "start_time": booked.start_time.strftime("%H:%M"),
                "end_time": booked.end_time.strftime("%H:%M")
            })

            added_booking_ids.add(booked.id)

            if len(slots) == 4:
                break

        return Response({
            "slots": slots,
            "location_id": court.location_id.id
        }, status=200)






    # def post(self, request):
    #     email = request.data.get("email", "").strip().lower()
    #     password = request.data.get("password")
    #     location_id = request.data.get("location_id")
    #     court_id = request.data.get("court_id")

    #     #  Validate required fields
    #     if not (email and password and location_id and court_id):
    #         return Response({
    #             "message": "Email, password, location_id, and court_id are required.",
    #             "code": 400
    #         }, status=200)

    #     try:
    #         location_id = int(location_id)
    #     except (TypeError, ValueError):
    #         return Response({
    #             "message": "Invalid location_id format.",
    #             "code": 400
    #         }, status=200)

    #     try:
    #         court_id = int(court_id)
    #     except (TypeError, ValueError):
    #         return Response({
    #             "message": "Invalid court_id format.",
    #             "code": 400
    #         }, status=200)

    #     # Use current time
    #     now = datetime.now()
    #     end_date = now + timedelta(days=7)

    #     try:
    #         user = User.objects.get(email__iexact=email, locations__id=location_id)
    #     except User.DoesNotExist:
    #         return Response({
    #             "message": "Invalid email or location.",
    #             "code": 400
    #         }, status=200)

    #     if not check_password(password, user.password):
    #         return Response({
    #             "message": "Incorrect password.",
    #             "code": 400
    #         }, status=200)

    #     try:
    #         court = Court.objects.get(id=court_id, location_id=location_id)
    #     except Court.DoesNotExist:
    #         return Response({
    #             "message": "Invalid court for this location.",
    #             "code": 400
    #         }, status=200)

    #     # Fetch bookings from now to next 7 days
    #     bookings = CourtBooking.objects.filter(
    #         court=court,
    #         booking_date__range=(now.date(), end_date.date())
    #     ).order_by("booking_date", "start_time")

    #     slots = []
    #     added_booking_ids = set()

    #     for booked in bookings:
    #         booking_start = datetime.combine(booked.booking_date, booked.start_time)
    #         if booking_start < now:
    #             continue  #  Skip past bookings

    #         if booked.id in added_booking_ids:
    #             continue

    #         slots.append({
    #             "code": len(slots) + 1,
    #             "court_id": court.id,
    #             "location_id": court.location_id.id,
    #             "court_number": court.court_number, 
    #             "booking_date": booked.booking_date.strftime("%Y-%m-%d"),
    #             "status": "BOOKED",
    #             "user_name": f"{booked.user.first_name} {booked.user.last_name}".strip(),
    #             "start_time": booked.start_time.strftime("%H:%M"),
    #             "end_time": booked.end_time.strftime("%H:%M")
    #         })

    #         added_booking_ids.add(booked.id)

    #         if len(slots) == 4:
    #             break

    #     return Response({
    #         "slots": slots,
    #         "location_id": court.location_id.id
    #     }, status=200)







class MyLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user  # Get the user from the token
        locations = user.locations.all()  # Queryset of assigned locations

        if not locations.exists():
            return Response({'error': 'Location not assigned to user'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UsersInMyLocationView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):
        current_user = request.user

        if not current_user.locations.exists():
            return Response({'error': 'You are not assigned to any location.'}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(locations__in=current_user.locations.all()).exclude(id=current_user.id).distinct()

        paginator = LargeResultsSetPagination()
        paginated_users = paginator.paginate_queryset(users, request)
        serializer = UserLoginFieldsSerializer(paginated_users, many=True)

        return paginator.get_paginated_response(serializer.data)




# class AdminCourtBookingListView(APIView):
#     permission_classes = [IsAuthenticated]


#     def get(self, request):
#         admin = request.user

#         if admin.user_type != 1:
#             raise PermissionDenied("Only admins can access this data.")

#         # Step 1: Get location IDs assigned to admin
#         assigned_location_ids = admin.locations.values_list('id', flat=True)

#         if not assigned_location_ids:
#             return Response({
#                 "message": "Admin is not assigned to any location.",
#                 "status_code": 400
#             }, status=400)

#         #  Step 2: Get courts in those locations
#         court_ids = Court.objects.filter(location_id__in=assigned_location_ids).values_list('id', flat=True)

#         if not court_ids:
#             return Response({
#                 "message": "No courts found for assigned locations.",
#                 "status_code": 200,
#                 "results": []
#             }, status=200)

#         #  Step 3: Filter bookings
#         bookings = CourtBooking.objects.filter(
#             court_id__in=court_ids,
#             user__locations__id__in=assigned_location_ids
#         ).select_related('court', 'user').distinct()

#         #  Step 4: Time-based filter
#         status_param = request.query_params.get('status')  # 'past' or 'upcoming'
#         now = timezone.now()
#         today = now.date()
#         time_now = now.time()

#         if status_param == 'past':
#             bookings = bookings.filter(
#                 Q(booking_date__lt=today) |
#                 Q(booking_date=today, end_time__lt=time_now)
#             )
#         elif status_param == 'upcoming':
#             bookings = bookings.filter(
#                 Q(booking_date__gt=today) |
#                 Q(booking_date=today, end_time__gte=time_now)
#             )


#         status_param = request.query_params.get('status')  # values: 'past', 'upcoming'
#         now = timezone.now()

#         if status_param == 'past':
#             bookings = bookings.filter(
#                 Q(booking_date__lt=now.date()) |
#                 Q(booking_date=now.date(), end_time__lt=now.time())
#             )
#         elif status_param == 'upcoming':
#             bookings = bookings.filter(
#                 Q(booking_date__gt=now.date()) |
#                 Q(booking_date=now.date(), end_time__gte=now.time())
#             )

#         # #  Step 4.5: Optional date range filter
#         start_date = request.query_params.get('start_date')
#         end_date = request.query_params.get('end_date')

#         if start_date and end_date:
#             start = parse_date(start_date)
#             end = parse_date(end_date)
#             if start and end:
#                 bookings = bookings.filter(booking_date__range=(start, end))




#         # Step 5: Optional search filter
#         search = request.query_params.get('search')
#         if search:
#             bookings = bookings.filter(
#                 Q(user__first_name__icontains=search) |
#                 Q(user__last_name__icontains=search) |
#                 Q(user__email__icontains=search) |
#                 Q(court__court_number__icontains=search)
#             )

#         #  Step 6: Order and paginate
#         bookings = bookings.order_by('booking_date', 'start_time')
#         paginator = LargeResultsSetPagination()
#         page = paginator.paginate_queryset(bookings, request)
#         serializer = AdminCourtBookingSerializer(page, many=True)

#         # Attach custom fields to paginated response
#         paginated_response = paginator.get_paginated_response(serializer.data)
#         paginated_response.data["message"] = "Court bookings fetched successfully."
#         paginated_response.data["status_code"] = 200

#         return paginated_response


class AdminCourtBookingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        admin = request.user

        if admin.user_type != 1:
            raise PermissionDenied("Only admins can access this data.")

        # Step 1: Get location IDs assigned to admin
        assigned_location_ids = admin.locations.values_list('id', flat=True)

        if not assigned_location_ids:
            return Response({
                "message": "Admin is not assigned to any location.",
                "status_code": 400
            }, status=400)

        # Step 2: Get courts in those locations
        court_ids = Court.objects.filter(location_id__in=assigned_location_ids).values_list('id', flat=True)

        if not court_ids:
            return Response({
                "message": "No courts found for assigned locations.",
                "status_code": 200,
                "results": []
            }, status=200)

        # Step 3: Filter bookings
        bookings = CourtBooking.objects.filter(
            court_id__in=court_ids,
            user__locations__id__in=assigned_location_ids
        ).select_related('court', 'user').distinct()


        # past and upcoming booking filter
        today = date.today()
        booking_type = request.query_params.get('type')  # 'past' or 'upcoming'

        if booking_type == 'past':
            bookings = bookings.filter(booking_date__lt=today).order_by('-booking_date')
        elif booking_type == 'upcoming':
            bookings = bookings.filter(booking_date__gte=today).order_by('booking_date')

        # Step 5: Optional search filter
        search = request.query_params.get('search')
        if search:
            bookings = bookings.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(court__court_number__icontains=search)
            )

        # Step 6: Order and paginate
        bookings = bookings.order_by('booking_date', 'start_time')
        paginator = LargeResultsSetPagination()
        page = paginator.paginate_queryset(bookings, request)
        serializer = AdminCourtBookingSerializer(page, many=True)

        # Attach custom fields to paginated response
        paginated_response = paginator.get_paginated_response(serializer.data)
        paginated_response.data["message"] = "Court bookings fetched successfully."
        paginated_response.data["status_code"] = 200

        return paginated_response





class GetLocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


    def get_queryset(self):
        # Return only unassigned locations
        queryset = Location.objects.filter()

        # Optional filter by date
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                queryset = queryset.filter(created_at__date__range=(start, end))

        return queryset


class BookedLocationDropdownView(APIView):
    def get(self, request):
        # Get locations that have at least one booking
        booked_location_ids = CourtBooking.objects.values_list('court__location_id', flat=True).distinct()
        locations = Location.objects.filter(id__in=booked_location_ids)
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class LocationListView(viewsets.ModelViewSet):
    """
    Returns all locations without pagination or filters.
    """
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    pagination_class = None  # Disable pagination

    def get_queryset(self):
        return Location.objects.all() 
    


class UserBasicDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        search_query = request.query_params.get('search', '')

        if user.user_type == 0:  # SuperAdmin
            queryset = User.objects.filter(user_type__gte=2)

        elif user.user_type == 1:  # Admin
            # Step: Get users whose locations overlap with admin's locations
            admin_locations = user.locations.all()
            queryset = User.objects.filter(
                user_type__gte=2,
                locations__in=admin_locations
            ).exclude(id=user.id).distinct()

        else:  # Regular user (Coach, Player, etc.)
            queryset = User.objects.filter(id=user.id)

        # Optional search
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        # Pagination
        paginator = LargeResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = UserBasicDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)
    



from django.db.models import Value as V, CharField

class BookingListView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):
        user = request.user
        search = request.query_params.get('search', '')
        location = request.query_params.get('location', '')  # new param for address search
        export = request.query_params.get('export', '')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # 1. Get bookings based on user type
        if user.user_type == 0:  # SuperAdmin
            bookings = CourtBooking.objects.select_related('user', 'court__location_id')
        elif user.user_type == 1:  # Admin
            assigned_locations = user.locations.all()
            bookings = CourtBooking.objects.filter(
                Q(court__location_id__in=assigned_locations) | Q(user=user) 
            ).select_related('user', 'court__location_id')
        else:
            bookings = CourtBooking.objects.none()

        # 2. Apply search filter for name, email, phone
        if search:
            bookings = bookings.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__phone__icontains=search) |
                Q(court__location_id__name__icontains=search) |
                Q(court__court_number__icontains=search)
            )

        # 3. Apply location (address) filter using new `location` key
        if location:
            bookings = bookings.annotate(
                full_address=Concat(
                    'court__location_id__address_1', V(' '),
                    'court__location_id__address_2', V(' '),
                    'court__location_id__address_3', V(' '),
                    'court__location_id__address_4', V(' '),
                    'court__location_id__name',
                    output_field=CharField()
                )
            ).filter(full_address__icontains=location)

        # 4. Apply date filter
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                bookings = bookings.filter(booking_date__gte=start_date_obj)
            except ValueError:
                pass

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                bookings = bookings.filter(booking_date__lte=end_date_obj)
            except ValueError:
                pass

        # 5. Paginate and return JSON response
        paginator = LargeResultsSetPagination()
        paginated_qs = paginator.paginate_queryset(bookings, request)
        serializer = CourtBookingWithUserSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)
  
    


class DownloadCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        search = request.query_params.get('search', '')
        export = request.query_params.get('export', '')

        # 1. Get bookings based on user type
        if user.user_type == 0:  # SuperAdmin
            bookings = CourtBooking.objects.select_related('user', 'court__location_id')
        elif user.user_type == 1:  # Admin
            assigned_locations = user.locations.all()
            bookings = CourtBooking.objects.filter(
                Q(court__location_id__in=assigned_locations) | Q(user=user)
            ).select_related('user', 'court__location_id')
        else:
            bookings = CourtBooking.objects.none()

        # 2. Apply search filter
        if search:
            bookings = bookings.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__phone__icontains=search)
            )


        serializer = CourtBookingWithUserSerializer(bookings, many=True)
        return Response(serializer.data)



class DeletePendingBookingsAPIView(APIView):

    def delete(self, request):
        deleted_count, _ = CourtBooking.objects.filter(status='pending').delete()
        return Response({
            "message": f"{deleted_count} pending bookings deleted successfully."
        }, status=status.HTTP_200_OK)
    

class UserRegisterView(APIView):
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            MailUtils.send_verification_email(user)
            return Response({
                "message": "Please check your email to verify your account before logging in.",
                "status": status.HTTP_201_CREATED
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": "400",
            "errors": serializer.errors,
            "message": "User registration failed."
        }, status=status.HTTP_400_BAD_REQUEST)
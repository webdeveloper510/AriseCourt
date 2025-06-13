from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import *
from django.conf import settings
from .mail import MailUtils
from datetime import date
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
import random
from rest_framework import viewsets, filters
from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_date





# Create your views here.


class LargeResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10000
    

def get_tokens_for_user(user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


class UserCreateView(APIView):
    def post(self, request):
        user = UserSerializer(data=request.data)
        if user.is_valid():
            data=user.save()
            MailUtils.send_verification_email(data)
            return Response({
                "message": "Registration successful. A verification email has been sent.",
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
                    'errors': 'Email not verified. Please verify your email before logging in.',
                    'status_code': status.HTTP_403_FORBIDDEN
                }, status=status.HTTP_403_FORBIDDEN)
            token = get_tokens_for_user(user)
            user_data = UserLoginFieldsSerializer(user).data
            return Response({
                'token': token,
                'message': 'Login Successfully',
                'status_code': status.HTTP_200_OK,
                'data': user_data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'errors': 'Invalid credentials',
                'status_code': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
   
    
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
                return Response({'error': 'User with this email does not exist.'}, status=status.HTTP_404_NOT_FOUND)

            otp = str(random.randint(100000, 999999))
            user.verified_otp = otp
            user.save()

            MailUtils.send_password_reset_email(user)

            return Response({'message': 'Password reset OTP sent to email.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.verified_otp != str(otp):
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)
    

class ResendOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        
        otp = str(random.randint(100000, 999999))
        user.verified_otp = otp
        user.save()

        # Reuse your existing email sending function
        MailUtils.send_password_reset_email(user)

        return Response({"message": "OTP and reset link have been resent to the email."}, status=status.HTTP_200_OK)
    

class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "Validation failed.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                "code": 400,
                "message": "User not found.",
            }, status=status.HTTP_400_BAD_REQUEST)

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
        self.perform_create(serializer)
        return Response({"message": "Admin created successfully.","status_code": status.HTTP_201_CREATED,"data": serializer.data}, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({"message": "Admin updated successfully.","status_code": status.HTTP_200_OK,"data": serializer.data}, status=status.HTTP_200_OK)

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
    search_fields = ['user__first_name','user__last_name', 'user__email', 'user__phone']
    
    def list(self, request, *args, **kwargs):
        today = date.today()
        booking_type = request.query_params.get('type') 

        # Filter bookings based on user
        if request.user.is_superuser:
            bookings = CourtBooking.objects.all()
        else:
            bookings = CourtBooking.objects.filter(user=request.user)

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
                return Response({"error": "End time must be after start time."}, status=400)

            duration = str(end_time - start_time)
            data['duration_time'] = duration  

        except:
            return Response({"error": "Invalid time format. Use HH:MM:SS"}, status=400)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        serializer.save(user=request.user)

        return Response(serializer.data, status=201)
    
    
class ContactUsViewSet(viewsets.ModelViewSet):
    queryset = ContactUs.objects.all()
    serializer_class = ContactUsSerializer


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

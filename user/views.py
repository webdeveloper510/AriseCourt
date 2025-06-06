from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import *
from django.core.mail import send_mail
from django.conf import settings
from .mail import MailUtils
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.template.loader import render_to_string
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


# Create your views here.

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
    
    
    

class VerifyEmailView(View):
    def get(self,request, uuid):
        user = get_object_or_404(User, uuid=uuid)
        
        if user.is_verified:
            return HttpResponse("Your email is already verified.")

        user.is_verified = True
        user.save()
        return HttpResponse("Email verified successfully! You can now log in.")




class UserLoginView(APIView):
    def post(self, request, format=None):

        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get('email')
        phone = serializer.validated_data.get('phone')
        password = serializer.validated_data.get('password')

        user = authenticate(email=email,password=password)

        if user is not None:
            token = get_tokens_for_user(user)
            return Response({'token':token,'msg':'Login Success'}, status=status.HTTP_200_OK)
        else:
            return Response({'errors': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)


       
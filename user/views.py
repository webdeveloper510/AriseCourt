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


# Create your views here.


class UserCreateView(APIView):
    def post(self, request):
        user = UserSerializer(data=request.data)
        if user.is_valid():
            user.save()
            MailUtils.send_verification_email(user)
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


from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import smart_str, force_bytes, DjangoUnicodeDecodeError
import random
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from .mail import MailUtils


class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')  
        password = validated_data.pop('password') 
        user = User(**validated_data)
        user.set_password(password) 
        user.save()
        return user





class UserLoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True)



class PasswordResetEmailSerializer(serializers.Serializer):
  class Meta:
    fields = ['email']

    def validate(self, data):
        email = data.get('email')
        try:
            user = User.objects.get(email=email)
        except user.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")


        otp = str(random.randint(100000, 999999))
        user.verified_otp = otp
        user.save()

        MailUtils.send_password_reset_email(user)
        return data



    



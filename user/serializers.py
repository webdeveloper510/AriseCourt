from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import smart_str, force_bytes, DjangoUnicodeDecodeError
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from .mail import MailUtils
from django.contrib.auth.hashers import make_password


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


class UserLoginFieldsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','first_name','last_name','user_type','phone','country','is_verified','email']
    

class AdminRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'user_type', 'password', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True},
            'user_type': {'default': 1}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True)


class PasswordResetEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, write_only=True)
    password = serializers.CharField(max_length=255,write_only=True)
    password2 = serializers.CharField(max_length=255,write_only=True)

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data


class LocationSerializer(serializers.ModelSerializer):
    courts = serializers.SerializerMethodField()
    class Meta:
        model = Location
        fields = '__all__'

    def get_courts(self, obj):
        courts = Court.objects.filter(location_id=obj.id)
        return CourtSerializer(courts, many=True).data    


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = '__all__'


class UserDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'user_type']


class CourtDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ['court_number', 'court_fee_hrs', 'tax','availability']


class CourtBookingSerializer(serializers.ModelSerializer):
    user = UserDataSerializer(read_only=True)
    court = CourtDataSerializer(read_only=True)
    
    class Meta:
        model = CourtBooking
        fields = '__all__' 


class ContactUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUs
        fields = '__all__'
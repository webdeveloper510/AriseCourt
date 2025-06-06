from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model



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



class UserLoginSerializer(serializers.ModelSerializer):
  class Meta:
    model = User
    fields = ['email', 'phone', 'password']

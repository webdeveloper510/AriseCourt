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
from datetime import datetime, timedelta


class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True}
        }



    def validate_first_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("First name should contain only letters.")
        return value

    def validate_last_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Last name should contain only letters.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_phone(self, value):
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError("Phone number must be 10 digits.")
        return value

    def validate_country(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Country name should only contain letters.")
        return value

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
    access_flag = serializers.CharField(source='adminpermission.access_flag', read_only=True)

    class Meta:
        model = User
        fields = ['id','first_name','last_name','user_type','phone','is_verified','email','access_flag']
    


class AdminRegistrationSerializer(serializers.ModelSerializer):
    access_flag = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'user_type', 'password', 'created_at', 'updated_at','access_flag']
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
    
    def get_access_flag(self, obj):
        try:
            permission = AdminPermission.objects.get(user=obj)
            return permission.access_flag
        except AdminPermission.DoesNotExist:
            return None
    


class UserLoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True)



class PasswordResetEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()



class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    new_password = serializers.CharField(max_length=255,write_only=True)
    confirm_password = serializers.CharField(max_length=255,write_only=True)

    class Meta:
        model = PasswordResetOTP
        fields = '__all__'

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data






class LocationSerializer(serializers.ModelSerializer):
    courts = serializers.SerializerMethodField()
    logo = serializers.ImageField(use_url=True)

    class Meta:
        model = Location
        fields = '__all__'

    # def get_courts(self, obj):
    #     courts = Court.objects.filter(location_id=obj.id)
    #     return CourtSerializer(courts, many=True).data 
    def get_courts(self, obj):
        courts = Court.objects.filter(location_id=obj.id)
        data = CourtSerializer(courts, many=True).data
        for court in data:
            court['court_id'] = court.pop('id')  # Rename 'id' to 'court_id'
        return data



class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = '__all__'



class UserDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'user_type']



class LocationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['description', 'address_1', 'address_2', 'address_3', 'address_4']



class CourtDataSerializer(serializers.ModelSerializer):
    location = LocationDataSerializer(source='location_id', read_only=True)

    class Meta:
        model = Court
        fields = ['court_number', 'court_fee_hrs', 'tax', 'cc_fees', 'availability', 'location']




def calculate_total_fee(total_price, tax_percent, cc_fees_percent):
        total_price = float(total_price)
        tax_amount = total_price * float(tax_percent) / 100
        cc_fee_amount = total_price * float(cc_fees_percent) / 100
        total_amount = total_price + tax_amount + cc_fee_amount
        return {
            'tax': round(tax_amount, 2),
            'cc_fees': round(cc_fee_amount, 2),
            'total': round(total_amount, 2)
        } 
class CourtBookingSerializer(serializers.ModelSerializer):
    user = UserDataSerializer(read_only=True)
    court = CourtDataSerializer(read_only=True)
    court_id = serializers.PrimaryKeyRelatedField(
        queryset=Court.objects.all(), source='court', write_only=True
    )
    booking_id = serializers.IntegerField(source='id', read_only=True)

    amount = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    cc_fees = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = CourtBooking
        fields = [
            'booking_id', 'user', 'court', 'court_id', 'booking_date','book_for_six_months','total_price',
            'start_time', 'end_time', 'duration_time', 'status',
            'created_at', 'updated_at',
            'amount', 'tax', 'cc_fees', 'summary'
        ]
        
    
       
       
    def get_amount(self, obj):
        return float(obj.total_price)

    def get_tax(self, obj):
        tax_percent = float(obj.court.tax)
        data = calculate_total_fee(obj.total_price, tax_percent, obj.court.cc_fees)
        return f"{data['tax']} ({tax_percent}%)"

    def get_cc_fees(self, obj):
        cc_fees_percent = float(obj.court.cc_fees)
        data = calculate_total_fee(obj.total_price, obj.court.tax, cc_fees_percent)
        return f"{data['cc_fees']} ({cc_fees_percent}%)"

    def get_summary(self, obj):
        data = calculate_total_fee(obj.total_price, obj.court.tax, obj.court.cc_fees)
        return data['total']    
    


class ContactUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUs
        fields = '__all__'



class CourtBookingDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourtBooking
        fields = ['booking_date', 'start_time', 'duration_time']



class UserDataSerializer(serializers.ModelSerializer):
    court_bookings = CourtBookingDataSerializer(many=True, read_only=True)
    country = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'user_type', 'court_bookings', 'country']

    def get_country(self, obj):
        if obj.country:
            return obj.country.name  
        return None
    


class UpdateProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField (read_only = True)
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'image', 'phone', 'email']

    def update(self, instance, validated_data):
        for field in ['first_name', 'last_name', 'image', 'phone']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()
        return instance
    


class CourtBookingReportSerializer(serializers.ModelSerializer):
    location_id = serializers.IntegerField(source='court.location_id.id')
    description = serializers.CharField(source='court.location_id.description')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')
    phone = serializers.CharField(source='user.phone')
    duration_time = serializers.CharField()

    class Meta:
        model = CourtBooking
        fields = ['location_id','description','first_name','last_name','email','phone','duration','amount_paid',]

    def get_duration(self, obj):
        if obj.start_time and obj.end_time:
            start = datetime.combine(obj.booking_date, obj.start_time)
            end = datetime.combine(obj.booking_date, obj.end_time)
            return round((end - start).seconds / 3600, 2)
        return None
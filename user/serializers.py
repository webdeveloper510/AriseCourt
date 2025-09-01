from rest_framework import serializers
from .models import *
import re
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
from decimal import Decimal, ROUND_DOWN, InvalidOperation,ROUND_HALF_UP
from datetime import datetime, timedelta




class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    location_id = serializers.IntegerField(write_only=True)
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
            'location': {'read_only': True} 
        }


    def validate_first_name(self, value):
        if not re.fullmatch(r"[A-Za-z ]+", value.strip()):
            raise serializers.ValidationError("First name can only contain letters and spaces.")
        return value.strip()

    def validate_last_name(self, value):
        if not re.fullmatch(r"[A-Za-z ]+", value.strip()):
            raise serializers.ValidationError("Last name can only contain letters and spaces.")
        return value.strip()

    def validate_email(self, value):
        value = value.lower()  
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
        location_id = validated_data.pop('location_id')
        validated_data['email'] = validated_data['email'].lower()

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Assign the many-to-many location
        try:
            location = Location.objects.get(id=location_id)
            user.locations.add(location)
        except Location.DoesNotExist:
            raise serializers.ValidationError({"location_id": "Invalid location ID."})

        return user


 
class UserLoginFieldsSerializer(serializers.ModelSerializer):
    access_flag = serializers.CharField(source='adminpermission.access_flag', read_only=True)

    class Meta:
        model = User
        fields = ['id','first_name','last_name','user_type','phone','is_verified','email','access_flag', 'locations']
    


class LocationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id','description', 'address_1', 'address_2', 'address_3', 'address_4','name', 'city', 'state', 'country']



class AdminRegistrationSerializer(serializers.ModelSerializer):
    access_flag = serializers.SerializerMethodField()
    location_id = serializers.IntegerField(write_only=True)
    country = serializers.CharField(required=False)
    locations = LocationDataSerializer(many=True, read_only=True) 

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone',
            'user_type', 'password','locations','location_id',
            'created_at', 'updated_at', 'access_flag','country'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'user_type': {'default': 1}
        }
    def create(self, validated_data):
        password = validated_data.pop('password')
        location_id = validated_data.pop('location_id')

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Correct way to assign ManyToMany location
        user.locations.add(location_id)
        return user
   
    def get_access_flag(self, obj):
        try:
            permission = AdminPermission.objects.get(user=obj)
            return permission.access_flag
        except AdminPermission.DoesNotExist:
            return None
        
    # def update(self, instance, validated_data):
    #     location_id = self.context['request'].data.get('location_id')
    #     if location_id:
    #         try:
    #             location_obj = Location.objects.get(id=location_id)
    #             # Remove old ones and assign new location
    #             instance.locations.set([location_obj])
    #             # Activate this location and deactivate others
    #             Location.objects.exclude(id=location_obj.id).update(status=False)
    #             location_obj.status = True
    #             location_obj.save()
    #         except Location.DoesNotExist:
    #             pass  # Optionally handle the case where the location is not found

    #     validated_data.pop('locations', None)
    #     validated_data.pop('location_id', None)
    #     return super().update(instance, validated_data)

    


class UserLoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    location = serializers.IntegerField(required=False)

    def validate_email(self, value):
        return value.lower()



class PasswordResetEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()



class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    new_password = serializers.CharField(max_length=255,write_only=True)
    confirm_password = serializers.CharField(max_length=255,write_only=True)

    class Meta:
        model = PasswordResetOTP
        fields = '__all__'

    def validate_email(self, value):
        return value.strip().lower()

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
        fields = ['first_name', 'last_name', 'email', 'phone', 'user_type','country']



class LocationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['description', 'address_1', 'address_2', 'address_3', 'address_4','name', 'city', 'state', 'country']



class CourtDataSerializer(serializers.ModelSerializer):
    location = LocationDataSerializer(source='location_id', read_only=True)
    court_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Court
        fields = ['court_id','court_number', 'court_fee_hrs', 'tax', 'cc_fees', 'availability', 'location']




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
    queryset=Court.objects.all(), source='court', write_only=True)
    booking_id = serializers.IntegerField(source='id', read_only=True)
    
    amount = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    cc_fees = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    full_cc_fees = serializers.SerializerMethodField()
    full_tax = serializers.SerializerMethodField() 

    class Meta:
        model = CourtBooking
        fields = [
            'booking_id', 'user', 'court', 'court_id', 'booking_date','book_for_four_weeks','total_price',
            'start_time', 'end_time', 'duration_time', 'status',
            'created_at', 'updated_at','on_amount','summary','amount',
         'tax', 'cc_fees','address','full_cc_fees','full_tax'
        ]
       
   

    def get_amount(self, obj):
        try:
            new_obj = obj.total_price
            return float(obj.total_price or 0)
        except (ValueError, TypeError):
            return 0.0
        

    def get_address(self, obj):
        location = obj.court.location_id
        # Combine all address parts, remove empty ones, and join with commas
        parts = [location.address_1, location.address_2, location.address_3, location.address_4]
        return ", ".join([p for p in parts if p])     



    def get_on_amount(self, obj):
        try:
            base_price = float(obj.total_price or 0)
            tax_percent = float(obj.court.tax or 0)
            cc_fees_percent = float(obj.court.cc_fees or 0)
            tax_amount = base_price * (tax_percent / 100)
            cc_fee_amount = base_price * (cc_fees_percent / 100)
            final_amount = base_price + tax_amount + cc_fee_amount
            return final_amount  # Full precision
        except (ValueError, TypeError, AttributeError):
            return 0.0


    def get_summary(self, obj):
        try:
            return round(self.get_on_amount(obj), 2)
        except:
            return 0.00
        

    def get_duration_time(self, obj):
        """Calculate duration in hours (decimal) for TimeField."""
        if obj.start_time and obj.end_time:
            # convert times to datetime objects on same date
            today = datetime.today().date()
            start_dt = datetime.combine(today, obj.start_time)
            end_dt = datetime.combine(today, obj.end_time)

            duration = (end_dt - start_dt).total_seconds() / 3600
            if duration < 0:  # handle overnight bookings
                duration += 24
            return round(duration, 2)
        return 0

    def get_total_price_based_on_duration(self, obj):
        """Calculate total base price = court_fee_hrs × duration."""
        duration = self.get_duration_time(obj)
        if obj.court and obj.court.court_fee_hrs:
            base_price = Decimal(str(obj.court.court_fee_hrs)) * Decimal(str(duration))
            return base_price.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return Decimal('0.00')

    def get_tax(self, obj):
        """Calculate tax as percentage of total price based on duration."""
        total_price = self.get_total_price_based_on_duration(obj)
        if obj.court and obj.court.tax:
            tax_percent = Decimal(str(obj.court.tax))
            tax_amount = (total_price * tax_percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            return f"{tax_amount:.2f} ({tax_percent:.2f}%)"
        return "0.00 (0%)"

    def get_cc_fees(self, obj):
        """Calculate cc fees as percentage of total price based on duration."""
        total_price = self.get_total_price_based_on_duration(obj)
        if obj.court and obj.court.cc_fees:
            cc_percent = Decimal(str(obj.court.cc_fees))
            cc_amount = (total_price * cc_percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            return f"{cc_amount:.2f} ({cc_percent:.2f}%)"
        return "0.00 (0%)"  
    
        
    def get_full_cc_fees(self, obj):
        try:
            base_price = float(obj.total_price or 0)
            cc_percent = float(obj.court.cc_fees or 0)
            cc_amount = round(base_price * cc_percent / 100, 2)
            return f"{cc_amount:.2f} ({cc_percent:.2f}%)"
        except:
            return "0.00 (0%)"


    def get_full_tax(self, obj):
        try:
            base_price = float(obj.total_price or 0)
            tax_percent = float(obj.court.tax or 0)
            tax_amount = round(base_price * tax_percent / 100, 2)
            return f"{tax_amount:.2f} ({tax_percent:.2f}%)"
        except:
            return "0.00 (0%)"


    


class ContactUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUs
        fields = '__all__'



class CourtBookingDataSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    court_number = serializers.SerializerMethodField()
    booking_day = serializers.SerializerMethodField()
    cc_fees = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    court_fee_hrs = serializers.SerializerMethodField() 
    # booked_on = serializers.SerializerMethodField()
    class Meta:
        model = CourtBooking
        fields = ['booking_date', 'start_time', 'duration_time', 'total_price', 'description','court_number','booking_day','cc_fees','tax','on_amount','created_at','court_fee_hrs']

    def get_description(self, obj):
        if obj.court and obj.court.location_id:
            return obj.court.location_id.description
        return None
    
    def get_court_number(self, obj):
        return getattr(obj.court, 'court_number', None)

    def get_booking_day(self, obj):
        return obj.created_at.date() if obj.created_at else None

    def get_cc_fees(self, obj):
        cc_fees_percent = 2.9  # Example CC fee %
        try:
            total_price = float(obj.total_price)
            return round(total_price * (cc_fees_percent / 100), 2)
        except (TypeError, ValueError):
            return 0.0

    def get_tax(self, obj):
        tax_percent = 5.0  # Example Tax %
        try:
            total_price = float(obj.total_price)
            return round(total_price * (tax_percent / 100), 2)
        except (TypeError, ValueError):
            return 0.0
        
    def get_court_fee_hrs(self, obj):
        try:
            return float(obj.court.court_fee_hrs)
        except (AttributeError, ValueError, TypeError):
            return 0.0
        






class UsersDataSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'user_type', 'country']
    def get_country(self, obj):
        return obj.country.name if obj.country else None

class CourtDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ['id', 'court_number', 'tax', 'cc_fees','court_fee_hrs']

class CourtBookingWithUserSerializer(serializers.ModelSerializer):
    user = UsersDataSerializer(read_only=True)
    court = CourtDataSerializer(read_only=True)
    tax = serializers.SerializerMethodField()
    cc_fees = serializers.SerializerMethodField()

    class Meta:
        model = CourtBooking
        fields = [
            'id', 'booking_date', 'start_time', 'end_time', 'duration_time',
            'total_price', 'on_amount', 'book_for_four_weeks', 'status',
            'created_at', 'updated_at', 'user', 'court','tax','cc_fees'
        ]


    def get_duration_time(self, obj):
        """Calculate duration in hours (decimal) for TimeField."""
        if obj.start_time and obj.end_time:
            # convert times to datetime objects on same date
            today = datetime.today().date()
            start_dt = datetime.combine(today, obj.start_time)
            end_dt = datetime.combine(today, obj.end_time)

            duration = (end_dt - start_dt).total_seconds() / 3600
            if duration < 0:  # handle overnight bookings
                duration += 24
            return round(duration, 2)
        return 0

    def get_total_price_based_on_duration(self, obj):
        """Calculate total base price = court_fee_hrs × duration."""
        duration = self.get_duration_time(obj)
        if obj.court and obj.court.court_fee_hrs:
            base_price = Decimal(str(obj.court.court_fee_hrs)) * Decimal(str(duration))
            return base_price.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return Decimal('0.00')

    def get_tax(self, obj):
        """Calculate tax as percentage of total price based on duration."""
        total_price = self.get_total_price_based_on_duration(obj)
        if obj.court and obj.court.tax:
            tax = total_price * Decimal(str(obj.court.tax)) / Decimal('100')
            return tax.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return Decimal('0.00')

    def get_cc_fees(self, obj):
        """Calculate cc fees as percentage of total price based on duration."""
        total_price = self.get_total_price_based_on_duration(obj)
        if obj.court and obj.court.cc_fees:
            cc = total_price * Decimal(str(obj.court.cc_fees)) / Decimal('100')
            return cc.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return Decimal('0.00')   

    # def get_tax(self, obj):
    #     """Calculate tax as percentage of total_price using court.tax without rounding"""
    #     if obj.on_amount and obj.court and obj.court.tax:
    #         tax = Decimal(str(obj.on_amount)) * Decimal(str(obj.court.tax)) / Decimal('100')
    #         return tax.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    #     return Decimal('0.00')

    # def get_cc_fees(self, obj):
    #     """Calculate cc_fees as percentage of total_price using court.cc_fees without rounding"""
    #     if obj.on_amount and obj.court and obj.court.cc_fees:
    #         cc = Decimal(str(obj.on_amount)) * Decimal(str(obj.court.cc_fees)) / Decimal('100')
    #         return cc.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    #     return Decimal('0.00')
 

    # def get_tax(self, obj):
    #     """Calculate tax as percentage of total_price using court.tax without rounding"""
    #     if obj.on_amount and obj.court and obj.court.tax:
    #         tax = Decimal(str(obj.on_amount)) * Decimal(str(obj.court.tax)) / Decimal('100')
    #         return tax.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    #     return Decimal('0.00')

    # def get_cc_fees(self, obj):
    #     """Calculate cc_fees as percentage of total_price using court.cc_fees without rounding"""
    #     if obj.on_amount and obj.court and obj.court.cc_fees:
    #         cc = Decimal(str(obj.on_amount)) * Decimal(str(obj.court.cc_fees)) / Decimal('100')
    #         return cc.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    #     return Decimal('0.00')
    


class UpdateProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField (read_only = True)
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'image', 'phone', 'email','EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']

    def update(self, instance, validated_data):
        for field in ['first_name', 'last_name', 'image', 'phone','EMAIL_HOST_USER','EMAIL_HOST_PASSWORD']:
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
    


class AdminCourtBookingSerializer(serializers.ModelSerializer):
    court_number = serializers.CharField(source='court.court_number', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_type = serializers.IntegerField(source='user.user_type', read_only=True)
    location_name = serializers.CharField(source='court.location_id.name', read_only=True)
    location_address = serializers.SerializerMethodField()


    # summary = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    cc_fees = serializers.SerializerMethodField()

    class Meta:
        model = CourtBooking
        fields = ['id','booking_date','start_time','end_time','duration_time','total_price','status','court_number','user_phone','user_first_name','user_last_name','user_email','user_type','location_name','location_address','on_amount','tax','cc_fees'
        ]

    def get_location_address(self, obj):
        location = obj.court.location_id
        parts = [
            location.address_1,
            location.address_2,
            location.address_3,
            location.address_4,
            location.city,
            location.state,
            location.country
        ]

        return ", ".join(filter(None, map(str.strip, filter(None, parts))))


    def get_tax(self, obj):
        try:
            tax_rate = Decimal(obj.court.tax or 0)
            total_price = Decimal(obj.total_price or 0)
            tax = (total_price * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            return f"{format_decimal(tax)} ({format_decimal(tax_rate)}%)"
        except Exception:
            return None

    def get_cc_fees(self, obj):
        try:
            cc_rate = Decimal(obj.court.cc_fees or 0)
            total_price = Decimal(obj.total_price or 0)
            cc_fee = (total_price * cc_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            return f"{format_decimal(cc_fee)} ({format_decimal(cc_rate)}%)"
        except Exception:
            return None

    def get_on_amount(self, obj):
        try:
            total_price = Decimal(obj.total_price or 0)
            tax = Decimal(obj.court.tax or 0)
            cc = Decimal(obj.court.cc_fees or 0)

            total_tax = (total_price * tax / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            total_cc = (total_price * cc / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            final_amount = (total_price + total_tax + total_cc).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

            return format_decimal(final_amount)
        except Exception:
            return None

    def get_total_price(self, obj):
        try:
            return format_decimal(Decimal(obj.total_price or 0))
        except Exception:
            return "0"

    




class UserBasicDataSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'user_type']

    
class UserRegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    location_id = serializers.IntegerField(write_only=True)
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
            'location': {'read_only': True} 
        }


    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        location_id = validated_data.pop('location_id')
        validated_data['email'] = validated_data['email'].lower()

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Assign the many-to-many location
        try:
            location = Location.objects.get(id=location_id)
            user.locations.add(location)
        except Location.DoesNotExist:
            raise serializers.ValidationError({"location_id": "Invalid location ID."})

        return user
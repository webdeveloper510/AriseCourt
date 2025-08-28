from django.db import models
from django.contrib.auth.models import AbstractBaseUser,  PermissionsMixin
from django_countries.fields import CountryField
from .managers import CustomUserManager
import uuid
from django.utils import timezone



# Create your models here.
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)


class User(BaseModel,AbstractBaseUser, PermissionsMixin):
    USER_TYPES = (
            (0, 'SuperAdmin'),
            (1, 'Admin'),
            (2, 'Coach'),
            (3, 'Player'),
            (4, 'Court'),
    )
    user_type = models.IntegerField(choices=USER_TYPES)
    image = models.ImageField(upload_to='profile_image',null=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    verification_token = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True,null=True)
    country = CountryField(blank_label='(select country)',null=True)
    password = models.CharField(max_length=1000)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_otp = models.CharField(max_length=6, null=True, blank=True)
    locations = models.ManyToManyField('Location', related_name='assigned_superadmins', blank=True)
    EMAIL_HOST_USER = models.CharField(max_length=225, null=True)
    EMAIL_HOST_PASSWORD =models.CharField(max_length=225, null=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email
    


class PasswordResetOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    expires_at = models.DateTimeField() 
    otp_verified = models.BooleanField(default=False)
    

class Location(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_locations', null=True)
    description = models.TextField()
    name = models.CharField(max_length=125, null=True, unique=True)
    logo = models.ImageField(upload_to='logo_image', null=True, blank=True)
    website = models.URLField(max_length=100,blank=True, null=True )
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128,null=True)
    address_1 = models.TextField()
    address_2 = models.TextField(blank=True, null=True)
    address_3 = models.TextField(blank=True, null=True)
    address_4 = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)


class Court(BaseModel):
    location_id = models.ForeignKey(Location, on_delete=models.CASCADE)
    court_number = models.CharField(max_length=30)
    court_fee_hrs = models.CharField(max_length=20)
    tax = models.CharField(max_length=100)
    cc_fees = models.CharField(max_length=100)  
    availability = models.BooleanField(default=False)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)


class CourtBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='court_bookings')
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='bookings')
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_time = models.CharField(blank=True, null=True,max_length=225)
    total_price = models.CharField(blank=True, null=True,max_length=225)
    on_amount = models.CharField(blank=True, null=True,max_length=225)
    book_for_four_weeks = models.BooleanField(default=False)
    parent_booking = models.CharField(null=True, max_length=225)
    status_choices = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='pending')
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)


class ContactUs(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=100)
    message = models.TextField()


class AdminPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_flag = models.CharField(max_length=10)


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_payments', null=True, blank=True)
    booking = models.ForeignKey(CourtBooking, on_delete=models.CASCADE, related_name='booking_payments', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', null=True, blank=True)
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    payment_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)



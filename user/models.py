from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django_countries.fields import CountryField
from .managers import CustomUserManager
import uuid

# Create your models here.
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)

class User(BaseModel,AbstractBaseUser):
    USER_TYPES = (
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
    phone = models.CharField(max_length=15, unique=True)
    country = CountryField(blank_label='(select country)')
    password = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_otp = models.CharField(max_length=6, null=True, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email
    
    

class PasswordResetOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    expires_at = models.DateTimeField() 
    otp_verified = models.BooleanField(default=False)
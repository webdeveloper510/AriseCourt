from django.contrib import admin
from . models import *

# Register your models here.

admin.site.register(User)
admin.site.register(Court)
admin.site.register(CourtBooking)
admin.site.register(Location)
admin.site.register(Payment)

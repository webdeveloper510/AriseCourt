from django.urls import path
from .views import DeviceListView, DeviceStatusView, DeviceToggleView

urlpatterns = [
    path("devices/", DeviceListView.as_view(), name="device-list"),
    path("devices/<str:device_id>/status/", DeviceStatusView.as_view(), name="device-status"),
    path("devices/<str:device_id>/toggle/", DeviceToggleView.as_view(), name="device-toggle"),
]

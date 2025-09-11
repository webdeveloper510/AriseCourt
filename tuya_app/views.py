from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .service import list_devices, get_device_status, send_device_command

class DeviceListView(APIView):
    """List all linked Tuya devices"""
    def get(self, request):
        devices = list_devices()
        return Response(devices, status=status.HTTP_200_OK)

class DeviceStatusView(APIView):
    """Get device status"""
    def get(self, request, device_id):
        status_data = get_device_status(device_id)
        return Response(status_data, status=status.HTTP_200_OK)

class DeviceToggleView(APIView):
    """Send ON/OFF command"""
    def post(self, request, device_id):
        code = request.data.get("code")     # e.g. "switch_led"
        value = request.data.get("value")   # true/false
        if not code or value is None:
            return Response(
                {"error": "Missing code or value"},
                status=status.HTTP_400_BAD_REQUEST
            )
        result = send_device_command(device_id, code, value)
        return Response(result, status=status.HTTP_200_OK)

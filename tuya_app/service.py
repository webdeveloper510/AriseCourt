from tinytuya import Cloud
import os


ACCESS_ID = "mqy4d7jx7kxwtdmkp7vw"       # API Key
ACCESS_KEY = "84ce9043ba894ef2ba9dbc94826632ec"  # API Secret
USERNAME = "sgupta1023@gmail.com"       # Tuya Smart/Smart Life app login
PASSWORD = "XandiP420@"                 # Tuya Smart/Smart Life password
API_REGION = "us"                       # region (us, eu, in, cn)

# Initialize Tuya Cloud
cloud = Cloud(
    apiRegion=API_REGION,
    apiKey=ACCESS_ID,
    apiSecret=ACCESS_KEY,
    username=USERNAME,
    password=PASSWORD,
)

def list_devices():
    """Get all devices"""
    devices = cloud.getdevices()
    print("Devices:", devices)
    print("999999999999999999",cloud.getdevices())
    return cloud.getdevices()

def get_device_status(device_id):
    """Get status of a device"""
    return cloud.getstatus(device_id)

def send_device_command(device_id, code, value):
    """Send ON/OFF or other commands to a device"""
    return cloud.sendcommand(
        device_id,
        {"commands": [{"code": code, "value": value}]},
        "devices/"
    )

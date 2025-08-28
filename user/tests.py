from django.test import TestCase

# Create your tests here.


from tinytuya import Cloud

# Replace with your Tuya Developer project credentials
ACCESS_ID = "mqy4d7jx7kxwtdmkp7vw"
ACCESS_KEY = "84ce9043ba894ef2ba9dbc94826632ec"
USERNAME = "sgupta1023@gmail.com"
PASSWORD = "XandiP420@"
API_REGION = "us"  # or 'eu', 'cn', 'in' depending on your region

# Initialize Tuya Cloud connection
cloud = Cloud(apiRegion=API_REGION,
              apiKey=ACCESS_ID,
              apiSecret=ACCESS_KEY,
              username=USERNAME,
              password=PASSWORD)

# Get all devices linked to your account
devices = cloud.getdevices()

if not devices:
    print("No devices found. Make sure your app is linked to your cloud project.")
    exit()

# Display device list (should be input in DB)
print("\nAvailable Devices:")
for i, dev in enumerate(devices):
    print(f"{i+1}. {dev['name']} - ID: {dev['id']}")

# Ask user to pick a device
choice = int(input("\nSelect a device by number: ")) - 1
if choice < 0 or choice >= len(devices):
    print("Invalid selection.")
    exit()

selected_device = devices[choice]
device_id = selected_device['id']

# Get DP codes
status = cloud.getstatus(device_id)
status = status['result']

# Try to find switch datapoint
dp_codes = []
for s in status:
    if 'switch' in s['code']:
        dp_codes.append(s)
if len(dp_codes) == 0:
    print("No switch found on this device.")
    exit()

# Ask user whether to turn ON or OFF
# Display device list
print("\nAvailable Switches:")
for i, code in enumerate(dp_codes):
    print("+++++")
    # print(f"{i+1}. {code['code']} status: {"on" if code['value'] else "off"}")

# Ask user to pick a switch (should be value in DB)
choice = int(input("\nSelect a switch by number: ")) - 1
if choice < 0 or choice >= len(dp_codes):
    print("Invalid selection.")
    exit()

on_off = input("Would you like to turn it on of off [on/off]? ")
on_off = on_off.lower()
if on_off not in ['on', 'off']:
    print('Invalid selection not in [on,off]')
    exit()
value = True if on_off == 'on' else False

# Send the command
result = cloud.sendcommand(device_id, {"commands": [
  {
    "code": dp_codes[choice]['code'],
    "value": value
  },
]}, "devices/")
print(f"\nCommand sent: {result}")
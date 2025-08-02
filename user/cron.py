import requests

def deletePendingBookings():
    try:
        delete_url = 'https://api.get1court.com/delete_pending_bookings/'
        response = requests.delete(delete_url)
        response.raise_for_status()
        print("Bookings Deleted Successfully.")
    except requests.RequestException as e:
        print(f"Failed to Delete bookings: {e}")
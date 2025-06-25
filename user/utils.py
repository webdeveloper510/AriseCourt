from datetime import datetime


def calculate_total_fee(court, duration_hours):
    base_fee = float(court.court_fee_hrs) * duration_hours
    tax = base_fee * 0.10
    cc_fee = base_fee * 0.10
    total = base_fee + tax + cc_fee
    return {
        "base_fee": base_fee,
        "tax": tax,
        "cc_fee": cc_fee,
        "total_amount": total
    }


def calculate_duration(start_time, end_time):
    fmt = "%H:%M:%S"
    start_dt = datetime.strptime(str(start_time), fmt)
    end_dt = datetime.strptime(str(end_time), fmt)
    duration = end_dt - start_dt
    return duration.total_seconds() / 3600 
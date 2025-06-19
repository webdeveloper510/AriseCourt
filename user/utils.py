from datetime import datetime


def calculate_total_fee(court, duration_hours):
    base_fee = float(court.court_fee_hrs) * duration_hours
    total = base_fee / 0.80
    tax = total * 0.10
    cc_fee = total * 0.10
    return {
        "total_amount": int(total * 100),
        "base_fee": base_fee,
        "tax": tax,
        "cc_fee": cc_fee
    }


def calculate_duration(start_time, end_time):
    fmt = "%H:%M:%S"
    start_dt = datetime.strptime(str(start_time), fmt)
    end_dt = datetime.strptime(str(end_time), fmt)
    duration = end_dt - start_dt
    return duration.total_seconds() / 3600 
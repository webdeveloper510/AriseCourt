from datetime import datetime

def calculate_total_fee(total_price, tax_percent, cc_fees_percent):
    total_price = float(total_price)
    tax_percent = float(tax_percent)
    cc_fees_percent = float(cc_fees_percent)
    tax_amount = total_price * (tax_percent / 100)
    cc_fee_amount = total_price * (cc_fees_percent / 100)
    total = total_price + tax_amount + cc_fee_amount
    return {"total_amount": total}


def calculate_duration(start_time, end_time):
    fmt = "%H:%M:%S"
    start_dt = datetime.strptime(str(start_time), fmt)
    end_dt = datetime.strptime(str(end_time), fmt)
    duration = end_dt - start_dt
    return duration.total_seconds() / 3600 
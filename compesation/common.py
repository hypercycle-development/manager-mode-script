from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
import time

USDC_CONTRACT_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
HYPC_CONTRACT_ADDRESS = "0xeA7B7DC089c9a4A916B5a7a37617f59fD54e37E4"
REFUND_WALLET_ADDRESSES = [
    "0x3Cb705Dad71DfeaFa928963B6fF21bF99FF4C2b9",
    "0x181615a6889e7cCD2DD4bf4375836351060704Db",
]
REFUND_WALLET_ADDRESSES_SET = {addr.lower() for addr in REFUND_WALLET_ADDRESSES}

tranche1_addresses_gist_id = "1d91a306014cab0eefea297feab97e54"
ETHERSCAN_API_KEY = "5BX4F2DJK5GXBEK62TCMFM9P86WD3RUFHR"

MAX_TIMESTAMP_UTC = 1754006400  # August 1, 2025
MAX_BLOCK_NUMBER = 23042514  # Exact block number for August 1, 2025

# Merklizer Mainnet
MERKLIZER_URL = "http://18.216.251.149:8003"


HTS_NODES = {
    "AWSTillingService1": {
        "url": "https://hyperpg.site/forward/52.73.19.138/8000",
        "address": "0x9F0c0D8759D8d14E8BE31919EA2739a6200B26B8",
    },
    "AWSTillingService2": {
        "url": "https://hyperpg.site/forward/18.236.42.238/8000",
        "address": "0x3b8B4E51A7AA83a848a355D234Df19A0391C933b",
    },
    "AWSTillingService3": {
        "url": "https://hyperpg.site/forward/35.163.52.26/8000",
        "address": "0xe0b9E3BF7463765eb55a3741feBdFEA3d50010Ab",
    },
    "AWSTillingService4": {
        "url": "https://hyperpg.site/forward/44.224.45.245/8000",
        "address": "0x612a58ec2483886e80859E56c595BA487F1aC349",
    },
    "AWSTillingService5": {
        "url": "https://hyperpg.site/forward/35.80.211.192/8000",
        "address": "0x1DE18E18d99f22b4280C16f4404e9933C2cbc377",
    },
    "AWSTillingService6": {
        "url": "https://hyperpg.site/forward/52.36.184.246/8000",
        "address": "0x77204F97Ae49De1464f08D9E07ae4359ACa636A6",
    },
}


def ctime_utc(timestamp):
    """Convert timestamp to human-readable UTC string"""
    return time.asctime(time.gmtime(timestamp))


def months_between_dates(init_date, final_date):
    # Convert timestamps to datetime objects in UTC (timezone-aware)
    start_date = datetime.fromtimestamp(init_date, tz=timezone.utc)
    end_date = datetime.fromtimestamp(final_date, tz=timezone.utc)

    # Calculate the difference in months with decimal precision
    delta = relativedelta(end_date, start_date)
    whole_months = delta.years * 12 + delta.months

    # Calculate the fractional part based on remaining days
    # Get the date after adding whole months
    intermediate_date = start_date + relativedelta(months=whole_months)
    remaining_days = (end_date - intermediate_date).days

    # Get days in the current month
    days_in_month = (
        intermediate_date + relativedelta(months=1) - intermediate_date
    ).days
    fractional_month = remaining_days / days_in_month

    return whole_months + fractional_month


def seconds_to_months(seconds):
    """
    Convert seconds to month
    """
    start_date = datetime(2023, 1, 1)
    end_date = start_date + timedelta(seconds=seconds)

    # Calculate months difference
    months = (end_date.year - start_date.year) * 12 + (
        end_date.month - start_date.month
    )

    # Add fractional month based on days
    days_in_month = (end_date.replace(day=1) + timedelta(days=32)).replace(
        day=1
    ) - timedelta(days=1)
    days_in_current_month = days_in_month.day
    fractional_month = end_date.day / days_in_current_month

    total_months = months + fractional_month
    return total_months

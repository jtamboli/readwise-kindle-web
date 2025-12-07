"""Sunrise/sunset calculation for dark mode support."""

import math
from datetime import datetime, timezone

# Hardcoded coordinates (Washington D.C. area)
LATITUDE = 39.003
LONGITUDE = -77.0425


def _calculate_sun_times(date: datetime) -> tuple[datetime, datetime]:
    """
    Calculate sunrise and sunset times for a given date.

    Uses the NOAA solar calculator algorithm (simplified).
    Returns (sunrise, sunset) as timezone-aware UTC datetimes.
    """
    # Day of year
    day_of_year = date.timetuple().tm_yday

    # Convert latitude to radians
    lat_rad = math.radians(LATITUDE)

    # Calculate solar declination (approximate)
    declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    decl_rad = math.radians(declination)

    # Calculate hour angle for sunrise/sunset
    # cos(hour_angle) = -tan(lat) * tan(decl)
    cos_hour_angle = -math.tan(lat_rad) * math.tan(decl_rad)

    # Clamp to valid range (handles polar day/night)
    cos_hour_angle = max(-1, min(1, cos_hour_angle))

    hour_angle = math.degrees(math.acos(cos_hour_angle))

    # Solar noon in hours (approximate, based on longitude)
    # Each 15 degrees of longitude = 1 hour offset from UTC
    solar_noon_utc = 12 - (LONGITUDE / 15)

    # Sunrise and sunset times in hours UTC
    sunrise_hour = solar_noon_utc - (hour_angle / 15)
    sunset_hour = solar_noon_utc + (hour_angle / 15)

    # Convert to datetime
    base_date = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

    sunrise_minutes = int(sunrise_hour * 60)
    sunset_minutes = int(sunset_hour * 60)

    sunrise = base_date.replace(
        hour=sunrise_minutes // 60,
        minute=sunrise_minutes % 60
    )
    sunset = base_date.replace(
        hour=sunset_minutes // 60,
        minute=sunset_minutes % 60
    )

    return sunrise, sunset


def is_dark_mode() -> bool:
    """
    Determine if dark mode should be enabled based on current time.

    Returns True if current time is before sunrise or after sunset.
    """
    now = datetime.now(timezone.utc)
    sunrise, sunset = _calculate_sun_times(now)

    return now < sunrise or now > sunset

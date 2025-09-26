"""Time-based calculator for adaptive lighting settings."""
from __future__ import annotations

import math
from datetime import datetime, time, timedelta
from typing import Any

from astral import LocationInfo
from astral.sun import sun
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


class TimeBasedCalculator:
    """Calculates adaptive brightness and color temperature based on time of day."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        min_brightness: int = 1,
        max_brightness: int = 255,
        min_color_temp: int = 2000,
        max_color_temp: int = 6500,
    ) -> None:
        """Initialize the calculator with brightness and color temperature ranges."""
        self.hass = hass
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_color_temp = min_color_temp
        self.max_color_temp = max_color_temp
        self._location_info = None
    
    def get_brightness_pct(self, dt: datetime | None = None) -> float:
        """Get brightness as percentage (0.0-1.0) based on time of day."""
        if dt is None:
            dt = dt_util.now()
        
        # Get sun position factor (0.0 = night, 1.0 = noon)
        sun_factor = self._get_sun_position_factor(dt)
        
        # Apply brightness curve with minimum at night
        min_pct = self.min_brightness / 255.0
        max_pct = self.max_brightness / 255.0
        
        # Use a smooth curve that provides good contrast between day and night
        brightness_pct = min_pct + (max_pct - min_pct) * sun_factor
        
        return max(min_pct, min(max_pct, brightness_pct))
    
    def get_brightness_value(self, dt: datetime | None = None) -> int:
        """Get brightness value (1-255) based on time of day."""
        brightness_pct = self.get_brightness_pct(dt)
        return int(brightness_pct * 255)
    
    def get_color_temp_kelvin(self, dt: datetime | None = None) -> int:
        """Get color temperature in Kelvin based on time of day."""
        if dt is None:
            dt = dt_util.now()
        
        # Get sun position factor (0.0 = night, 1.0 = noon)
        sun_factor = self._get_sun_position_factor(dt)
        
        # Invert for color temperature (warm at night, cool during day)
        temp_factor = sun_factor
        
        # Calculate color temperature
        color_temp = self.min_color_temp + (self.max_color_temp - self.min_color_temp) * temp_factor
        
        return int(max(self.min_color_temp, min(self.max_color_temp, color_temp)))
    
    def apply_white_balance_correction(
        self, 
        color_temp: int, 
        white_balance_offset: int = 0
    ) -> int:
        """
        Apply white balance correction to color temperature.
        
        Args:
            color_temp: Base color temperature in Kelvin
            white_balance_offset: Offset in Kelvin (-1000 to +1000)
            
        Returns:
            Corrected color temperature in Kelvin
        """
        corrected_temp = color_temp + white_balance_offset
        return int(max(self.min_color_temp, min(self.max_color_temp, corrected_temp)))
    
    def apply_brightness_factor(
        self, 
        brightness: int, 
        brightness_factor: float = 1.0
    ) -> int:
        """
        Apply brightness factor correction to brightness value.
        
        Args:
            brightness: Base brightness value (1-255)
            brightness_factor: Multiplication factor (0.1 to 2.0)
            
        Returns:
            Corrected brightness value (1-255)
        """
        corrected_brightness = int(brightness * brightness_factor)
        return max(1, min(255, corrected_brightness))
    
    def get_adaptive_settings(
        self, 
        dt: datetime | None = None,
        white_balance_offset: int = 0,
        brightness_factor: float = 1.0,
    ) -> dict[str, Any]:
        """
        Get complete adaptive settings with corrections applied.
        
        Args:
            dt: Datetime to calculate for (defaults to now)
            white_balance_offset: White balance offset in Kelvin
            brightness_factor: Brightness multiplication factor
            
        Returns:
            Dictionary with brightness and color_temp_kelvin keys
        """
        if dt is None:
            dt = dt_util.now()
        
        # Get base values
        base_brightness = self.get_brightness_value(dt)
        base_color_temp = self.get_color_temp_kelvin(dt)
        
        # Apply corrections
        corrected_brightness = self.apply_brightness_factor(base_brightness, brightness_factor)
        corrected_color_temp = self.apply_white_balance_correction(base_color_temp, white_balance_offset)
        
        return {
            "brightness": corrected_brightness,
            "color_temp_kelvin": corrected_color_temp,
        }
    
    def _get_location_info(self) -> LocationInfo:
        """Get location info from Home Assistant configuration."""
        if self._location_info is None:
            # Get location from Home Assistant config
            config = self.hass.config
            self._location_info = LocationInfo(
                name="Home Assistant",
                region="",
                timezone=str(config.time_zone),
                latitude=config.latitude,
                longitude=config.longitude,
            )
        return self._location_info
    
    def _get_sun_times(self, dt: datetime) -> dict[str, datetime]:
        """Get sun times for the given date."""
        location = self._get_location_info()
        
        try:
            # Get sun times for the date
            sun_times = sun(location.observer, date=dt.date())
            return {
                'sunrise': sun_times['sunrise'].replace(tzinfo=dt.tzinfo),
                'sunset': sun_times['sunset'].replace(tzinfo=dt.tzinfo),
                'noon': sun_times['noon'].replace(tzinfo=dt.tzinfo),
            }
        except Exception:
            # Fallback to default times if astral calculation fails
            date = dt.date()
            tz = dt.tzinfo
            return {
                'sunrise': datetime.combine(date, time(6, 0)).replace(tzinfo=tz),
                'sunset': datetime.combine(date, time(18, 0)).replace(tzinfo=tz),
                'noon': datetime.combine(date, time(12, 0)).replace(tzinfo=tz),
            }
    
    def _get_sun_position_factor(self, dt: datetime) -> float:
        """
        Calculate sun position factor based on actual sunrise/sunset times.
        
        Returns:
            float: 0.0 at night, 1.0 at solar noon, smooth transitions at sunrise/sunset
        """
        sun_times = self._get_sun_times(dt)
        sunrise = sun_times['sunrise']
        sunset = sun_times['sunset']
        noon = sun_times['noon']
        
        # Add transition periods for smooth curves
        transition_duration = timedelta(minutes=30)
        sunrise_start = sunrise - transition_duration
        sunrise_end = sunrise + transition_duration
        sunset_start = sunset - transition_duration
        sunset_end = sunset + transition_duration
        
        if dt < sunrise_start or dt > sunset_end:
            # Deep night
            return 0.0
        elif sunrise_start <= dt < sunrise_end:
            # Sunrise transition (smooth curve from 0 to peak)
            progress = (dt - sunrise_start).total_seconds() / (2 * transition_duration.total_seconds())
            return 0.5 * (1 - math.cos(progress * math.pi))
        elif sunrise_end <= dt < sunset_start:
            # Day time - use sine curve peaking at solar noon
            day_duration = (sunset_start - sunrise_end).total_seconds()
            if day_duration > 0:
                day_progress = (dt - sunrise_end).total_seconds() / day_duration
                # Sine curve from 0.5 to 1.0 and back to 0.5
                return 0.5 + 0.5 * math.sin((day_progress - 0.5) * math.pi)
            else:
                return 1.0
        elif sunset_start <= dt <= sunset_end:
            # Sunset transition (smooth curve from peak to 0)
            progress = (dt - sunset_start).total_seconds() / (2 * transition_duration.total_seconds())
            return 0.5 * (1 + math.cos(progress * math.pi))
        
        return 0.0
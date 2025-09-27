"""Adaptive Lighting Manager for coordinating the integration components."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .calculator import TimeBasedCalculator
from .const import (
    CONF_LIGHTS,
    DEFAULT_MAX_COLOR_TEMP,
    DEFAULT_MIN_COLOR_TEMP,
)
from .models import AdaptiveSettings, LightConfig

_LOGGER = logging.getLogger(__name__)


class AdaptiveLightingManager:
    """Manages adaptive lighting for nominated lights."""
    
    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the adaptive lighting manager."""
        self.hass = hass
        self._config = config
        self._lights: dict[str, LightConfig] = {}
        self._calculator = TimeBasedCalculator(hass=hass)
        self._adaptive_enabled = True
        
        # Load light configurations
        for light_data in config.get(CONF_LIGHTS, []):
            light_config = LightConfig.from_dict(light_data)
            self._lights[light_config.entity_id] = light_config
            _LOGGER.debug("Loaded light config for %s: min=%dK, max=%dK", 
                         light_config.entity_id, light_config.min_color_temp, light_config.max_color_temp)
    
    async def setup(self) -> bool:
        """Set up the adaptive lighting manager."""
        _LOGGER.debug("Setting up adaptive lighting manager with %d lights", len(self._lights))
        return True
    
    def get_color_temp_for_light(self, entity_id: str, current_time: datetime | None = None) -> int:
        """
        Get color temperature for a specific light using Home Assistant sun data and per-light ranges.
        
        Args:
            entity_id: The light entity ID
            current_time: Optional datetime to calculate for (defaults to now)
            
        Returns:
            Color temperature in Kelvin within the light's configured range
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Get the light's configuration
        light_config = self._lights.get(entity_id)
        if not light_config:
            _LOGGER.warning("No configuration found for light %s, using defaults", entity_id)
            min_temp = DEFAULT_MIN_COLOR_TEMP
            max_temp = DEFAULT_MAX_COLOR_TEMP
        else:
            min_temp = light_config.min_color_temp
            max_temp = light_config.max_color_temp
        
        # Use the calculator with the light's specific range
        color_temp = self._calculator.get_color_temp_kelvin(current_time)
        
        # Apply the light's specific range constraints
        constrained_temp = max(min_temp, min(max_temp, color_temp))
        
        # Apply white balance correction if configured
        if light_config and light_config.white_balance_offset != 0:
            constrained_temp += light_config.white_balance_offset
            # Re-apply range constraints after white balance correction
            constrained_temp = max(min_temp, min(max_temp, constrained_temp))
        
        _LOGGER.debug("Color temp for %s: base=%dK, constrained=%dK (range: %dK-%dK)", 
                     entity_id, color_temp, constrained_temp, min_temp, max_temp)
        
        return constrained_temp
    
    def calculate_adaptive_settings(self, entity_id: str, current_time: datetime | None = None) -> AdaptiveSettings:
        """Calculate adaptive settings for a specific light entity."""
        if current_time is None:
            current_time = datetime.now()
        
        # Get adaptive color temperature using per-light ranges
        color_temp = self.get_color_temp_for_light(entity_id, current_time)
        
        # Get base brightness from calculator
        base_brightness = self._calculator.get_brightness_value(current_time)
        
        # Apply per-light brightness correction if configured
        light_config = self._lights.get(entity_id)
        if light_config and light_config.brightness_factor != 1.0:
            corrected_brightness = int(base_brightness * light_config.brightness_factor)
            corrected_brightness = max(1, min(255, corrected_brightness))
        else:
            corrected_brightness = base_brightness
        
        return AdaptiveSettings(
            brightness=corrected_brightness,
            color_temp_kelvin=color_temp,
            transition=1,
        )
    
    async def enable_adaptive_lighting(self) -> None:
        """Enable adaptive lighting globally."""
        if not self._adaptive_enabled:
            self._adaptive_enabled = True
            _LOGGER.debug("Adaptive lighting enabled globally")
    
    async def disable_adaptive_lighting(self) -> None:
        """Disable adaptive lighting globally."""
        if self._adaptive_enabled:
            self._adaptive_enabled = False
            _LOGGER.debug("Adaptive lighting disabled globally")
    
    def is_adaptive_enabled(self) -> bool:
        """Return whether adaptive lighting is enabled globally."""
        return self._adaptive_enabled
    
    def get_light_config(self, entity_id: str) -> LightConfig | None:
        """Get the configuration for a specific light."""
        return self._lights.get(entity_id)
    
    def get_light_corrections(self, entity_id: str) -> dict[str, Any]:
        """
        Get the corrections and configuration for a specific light.
        
        Args:
            entity_id: The light entity ID
            
        Returns:
            Dictionary with light configuration details
        """
        light_config = self._lights.get(entity_id)
        if not light_config:
            return {
                "min_color_temp": DEFAULT_MIN_COLOR_TEMP,
                "max_color_temp": DEFAULT_MAX_COLOR_TEMP,
                "white_balance_offset": 0,
                "brightness_factor": 1.0,
                "enabled": False,
            }
        
        return {
            "min_color_temp": light_config.min_color_temp,
            "max_color_temp": light_config.max_color_temp,
            "white_balance_offset": light_config.white_balance_offset,
            "brightness_factor": light_config.brightness_factor,
            "enabled": light_config.enabled,
        }
    
    def validate_light_ranges(self) -> bool:
        """
        Validate that all configured lights have valid color temperature ranges.
        
        Returns:
            True if all ranges are valid (min < max, reasonable bounds)
        """
        for entity_id, light_config in self._lights.items():
            # Check that min < max
            if light_config.min_color_temp >= light_config.max_color_temp:
                _LOGGER.error(
                    "Light %s has invalid color temperature range: min=%dK >= max=%dK",
                    entity_id, light_config.min_color_temp, light_config.max_color_temp
                )
                return False
            
            # Check reasonable bounds (1000K - 10000K)
            if not (1000 <= light_config.min_color_temp <= 10000):
                _LOGGER.error(
                    "Light %s has min color temperature %dK outside reasonable range (1000K-10000K)",
                    entity_id, light_config.min_color_temp
                )
                return False
            
            if not (1000 <= light_config.max_color_temp <= 10000):
                _LOGGER.error(
                    "Light %s has max color temperature %dK outside reasonable range (1000K-10000K)",
                    entity_id, light_config.max_color_temp
                )
                return False
            
            # Check white balance offset range
            if not (-1000 <= light_config.white_balance_offset <= 1000):
                _LOGGER.warning(
                    "Light %s has white balance offset %dK outside recommended range (-1000K to 1000K)",
                    entity_id, light_config.white_balance_offset
                )
            
            # Check brightness factor range
            if not (0.1 <= light_config.brightness_factor <= 2.0):
                _LOGGER.warning(
                    "Light %s has brightness factor %.2f outside recommended range (0.1 to 2.0)",
                    entity_id, light_config.brightness_factor
                )
        
        return True
    
    @property
    def configured_lights(self) -> list[str]:
        """Return list of configured light entity IDs."""
        return list(self._lights.keys())
    
    def get_adaptive_state_summary(self) -> dict[str, Any]:
        """Get a summary of the adaptive lighting state across all entities."""
        return {
            "adaptive_enabled": self._adaptive_enabled,
            "total_lights": len(self._lights),
            "enabled_lights": sum(1 for config in self._lights.values() if config.enabled),
            "lights": {
                entity_id: {
                    "enabled": config.enabled,
                    "min_color_temp": config.min_color_temp,
                    "max_color_temp": config.max_color_temp,
                    "current_color_temp": self.get_color_temp_for_light(entity_id) if config.enabled else None,
                }
                for entity_id, config in self._lights.items()
            }
        }
"""Adaptive Lighting Manager for coordinating the integration components."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_get_all_descriptions

from .calculator import TimeBasedCalculator
from .const import (
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_COLOR_TEMP,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP,
    SERVICE_LIGHT_TOGGLE,
    SERVICE_LIGHT_TURN_ON,
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
        self._calculator = TimeBasedCalculator(
            hass=hass,
            min_brightness=config.get(CONF_MIN_BRIGHTNESS, 1),
            max_brightness=config.get(CONF_MAX_BRIGHTNESS, 255),
            min_color_temp=config.get(CONF_MIN_COLOR_TEMP, 2000),
            max_color_temp=config.get(CONF_MAX_COLOR_TEMP, 6500),
        )
        self._interception_enabled = False
        self._original_handlers: dict[str, Any] = {}
        
        # Load light configurations
        for light_data in config.get(CONF_LIGHTS, []):
            light_config = LightConfig.from_dict(light_data)
            self._lights[light_config.entity_id] = light_config
    
    async def setup(self) -> bool:
        """Set up the adaptive lighting manager."""
        _LOGGER.debug("Setting up adaptive lighting manager")
        return True
    
    async def enable_interception(self) -> None:
        """Enable service call interception for adaptive lighting."""
        if self._interception_enabled:
            return
        
        try:
            # Store original service handlers
            services = self.hass.services
            
            # Intercept light.turn_on
            if services.has_service("light", "turn_on"):
                self._original_handlers[SERVICE_LIGHT_TURN_ON] = services._services["light"]["turn_on"]
                services.async_remove("light", "turn_on")
                services.async_register(
                    "light",
                    "turn_on",
                    self._async_intercept_turn_on,
                    schema=self._original_handlers[SERVICE_LIGHT_TURN_ON].schema,
                )
            
            # Intercept light.toggle
            if services.has_service("light", "toggle"):
                self._original_handlers[SERVICE_LIGHT_TOGGLE] = services._services["light"]["toggle"]
                services.async_remove("light", "toggle")
                services.async_register(
                    "light",
                    "toggle",
                    self._async_intercept_toggle,
                    schema=self._original_handlers[SERVICE_LIGHT_TOGGLE].schema,
                )
            
            self._interception_enabled = True
            _LOGGER.debug("Service call interception enabled")
            
        except Exception as err:
            _LOGGER.error("Failed to enable service interception: %s", err)
            await self.disable_interception()
    
    async def disable_interception(self) -> None:
        """Disable service call interception."""
        if not self._interception_enabled:
            return
        
        try:
            services = self.hass.services
            
            # Restore original handlers
            for service_name, handler in self._original_handlers.items():
                domain, service = service_name.split(".", 1)
                services.async_remove(domain, service)
                services.async_register(
                    domain,
                    service,
                    handler.job.target,
                    schema=handler.schema,
                )
            
            self._original_handlers.clear()
            self._interception_enabled = False
            _LOGGER.debug("Service call interception disabled")
            
        except Exception as err:
            _LOGGER.error("Failed to disable service interception: %s", err)
    
    async def _async_intercept_turn_on(self, call: ServiceCall) -> None:
        """Intercept light.turn_on service calls."""
        await self._async_intercept_service_call(call, SERVICE_LIGHT_TURN_ON)
    
    async def _async_intercept_toggle(self, call: ServiceCall) -> None:
        """Intercept light.toggle service calls."""
        await self._async_intercept_service_call(call, SERVICE_LIGHT_TOGGLE)
    
    async def async_intercept_service_call(self, call: ServiceCall) -> None:
        """
        Process intercepted light commands and apply adaptive settings.
        
        This is the main method that processes intercepted service calls,
        calculates adaptive settings, and applies them to nominated lights.
        """
        try:
            # Determine which service was called
            service_name = f"{call.domain}.{call.service}"
            
            # Get the original handler
            original_handler = self._original_handlers.get(service_name)
            if not original_handler:
                _LOGGER.error("No original handler found for %s", service_name)
                return
            
            # Check if any targeted entities are adaptive lights
            entity_ids = call.data.get("entity_id", [])
            if isinstance(entity_ids, str):
                entity_ids = [entity_ids]
            elif entity_ids is None:
                entity_ids = []
            
            adaptive_entities = [eid for eid in entity_ids if eid in self._lights and self._lights[eid].enabled]
            
            if not adaptive_entities:
                # No adaptive lights targeted, pass through unchanged
                await original_handler.job.target(call)
                return
            
            _LOGGER.debug("Applying adaptive settings to entities: %s", adaptive_entities)
            
            # Handle multiple entities by making individual calls with adaptive settings
            if len(entity_ids) == 1 and entity_ids[0] in adaptive_entities:
                # Single adaptive entity - modify the call data directly
                entity_id = entity_ids[0]
                adaptive_settings = self.calculate_adaptive_settings(entity_id)
                
                modified_data = dict(call.data)
                modified_data.update(adaptive_settings.to_service_data())
                
                modified_call = ServiceCall(
                    domain=call.domain,
                    service=call.service,
                    data=modified_data,
                    context=call.context,
                )
                
                await original_handler.job.target(modified_call)
                
            else:
                # Multiple entities - separate adaptive and non-adaptive calls
                non_adaptive_entities = [eid for eid in entity_ids if eid not in adaptive_entities]
                
                # Call non-adaptive entities with original data
                if non_adaptive_entities:
                    non_adaptive_data = dict(call.data)
                    non_adaptive_data["entity_id"] = non_adaptive_entities
                    
                    non_adaptive_call = ServiceCall(
                        domain=call.domain,
                        service=call.service,
                        data=non_adaptive_data,
                        context=call.context,
                    )
                    
                    await original_handler.job.target(non_adaptive_call)
                
                # Call each adaptive entity individually with adaptive settings
                for entity_id in adaptive_entities:
                    adaptive_settings = self.calculate_adaptive_settings(entity_id)
                    
                    adaptive_data = dict(call.data)
                    adaptive_data["entity_id"] = entity_id
                    adaptive_data.update(adaptive_settings.to_service_data())
                    
                    adaptive_call = ServiceCall(
                        domain=call.domain,
                        service=call.service,
                        data=adaptive_data,
                        context=call.context,
                    )
                    
                    await original_handler.job.target(adaptive_call)
            
        except Exception as err:
            _LOGGER.error("Error in service call interception: %s", err)
            # Fallback to original call to avoid breaking light controls
            service_name = f"{call.domain}.{call.service}"
            if service_name in self._original_handlers:
                await self._original_handlers[service_name].job.target(call)

    async def _async_intercept_service_call(self, call: ServiceCall, service_name: str) -> None:
        """Internal method to route service calls to the main interception handler."""
        await self.async_intercept_service_call(call)
    
    def calculate_adaptive_settings(self, entity_id: str, current_time: datetime | None = None) -> AdaptiveSettings:
        """Calculate adaptive settings for a specific light entity."""
        if current_time is None:
            current_time = datetime.now()
        
        # Get base adaptive settings from calculator
        base_brightness = self._calculator.get_brightness_value(current_time)
        base_color_temp = self._calculator.get_color_temp_kelvin(current_time)
        
        # Apply per-light corrections if configured
        corrected_brightness = self.apply_brightness_correction(entity_id, base_brightness)
        corrected_color_temp = self.apply_white_balance(entity_id, base_color_temp)
        
        return AdaptiveSettings(
            brightness=corrected_brightness,
            color_temp_kelvin=corrected_color_temp,
            transition=1,
        )
    
    def apply_brightness_correction(self, entity_id: str, base_brightness: int) -> int:
        """
        Apply brightness factor correction to base brightness value.
        
        Args:
            entity_id: The light entity ID
            base_brightness: Base brightness value (1-255)
            
        Returns:
            Corrected brightness value (1-255)
        """
        if entity_id not in self._lights:
            return base_brightness
        
        light_config = self._lights[entity_id]
        corrected_brightness = int(base_brightness * light_config.brightness_factor)
        
        # Clamp to valid range
        return max(1, min(255, corrected_brightness))
    
    def apply_white_balance(self, entity_id: str, base_color_temp: int) -> int:
        """
        Apply white balance correction to base color temperature.
        
        Args:
            entity_id: The light entity ID
            base_color_temp: Base color temperature in Kelvin
            
        Returns:
            Corrected color temperature in Kelvin
        """
        if entity_id not in self._lights:
            return base_color_temp
        
        light_config = self._lights[entity_id]
        corrected_temp = base_color_temp + light_config.white_balance_offset
        
        # Clamp to reasonable range (use calculator's configured range if available)
        min_temp = getattr(self._calculator, 'min_color_temp', 1000)
        max_temp = getattr(self._calculator, 'max_color_temp', 10000)
        
        return max(min_temp, min(max_temp, corrected_temp))
    
    @property
    def is_interception_enabled(self) -> bool:
        """Return whether service call interception is enabled."""
        return self._interception_enabled
    
    def get_light_corrections(self, entity_id: str) -> dict[str, Any]:
        """
        Get the white balance and brightness corrections for a specific light.
        
        Args:
            entity_id: The light entity ID
            
        Returns:
            Dictionary with white_balance_offset and brightness_factor
        """
        if entity_id not in self._lights:
            return {
                "white_balance_offset": 0,
                "brightness_factor": 1.0,
                "enabled": False,
            }
        
        light_config = self._lights[entity_id]
        return {
            "white_balance_offset": light_config.white_balance_offset,
            "brightness_factor": light_config.brightness_factor,
            "enabled": light_config.enabled,
        }
    
    def validate_corrections_consistency(self) -> bool:
        """
        Validate that all configured lights have consistent correction settings.
        
        Returns:
            True if all corrections are within valid ranges
        """
        for entity_id, light_config in self._lights.items():
            # Check white balance offset range
            if not (-1000 <= light_config.white_balance_offset <= 1000):
                _LOGGER.warning(
                    "Light %s has white balance offset %d outside recommended range (-1000 to 1000)",
                    entity_id, light_config.white_balance_offset
                )
                return False
            
            # Check brightness factor range
            if not (0.1 <= light_config.brightness_factor <= 2.0):
                _LOGGER.warning(
                    "Light %s has brightness factor %.2f outside recommended range (0.1 to 2.0)",
                    entity_id, light_config.brightness_factor
                )
                return False
        
        return True
    
    @property
    def configured_lights(self) -> list[str]:
        """Return list of configured light entity IDs."""
        return list(self._lights.keys())
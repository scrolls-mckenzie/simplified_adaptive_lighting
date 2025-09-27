"""Adaptive light entity that can be controlled by HomeKit."""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .calculator import TimeBasedCalculator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AdaptiveLight(LightEntity, RestoreEntity):
    """An adaptive light entity that controls a target light with time-based settings."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_entity_id: str,
        name: str,
        white_balance_offset: int = 0,
        brightness_factor: float = 1.0,
    ) -> None:
        """Initialize the adaptive light."""
        self.hass = hass
        self._target_entity_id = target_entity_id
        self._name = name
        self._white_balance_offset = white_balance_offset
        self._brightness_factor = brightness_factor
        
        self._calculator = TimeBasedCalculator(hass)
        self._is_on = False
        self._brightness = 255
        self._color_temp = 3000
        
        # Generate unique ID based on target entity
        self._attr_unique_id = f"adaptive_{target_entity_id.replace('.', '_')}"

    @property
    def name(self) -> str:
        """Return the name of the adaptive light."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if the adaptive light is on."""
        return self._is_on

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of the adaptive light."""
        return self._brightness if self._is_on else None

    @property
    def color_temp(self) -> Optional[int]:
        """Return the color temperature of the adaptive light."""
        return self._color_temp if self._is_on else None

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {ColorMode.COLOR_TEMP}

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        return ColorMode.COLOR_TEMP

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the adaptive light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=f"Adaptive {self._name}",
            manufacturer="Simplified Adaptive Lighting",
            model="Adaptive Light Controller",
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
            if last_state.attributes.get(ATTR_BRIGHTNESS):
                self._brightness = last_state.attributes[ATTR_BRIGHTNESS]
            if last_state.attributes.get(ATTR_COLOR_TEMP_KELVIN):
                self._color_temp = last_state.attributes[ATTR_COLOR_TEMP_KELVIN]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the adaptive light and apply adaptive settings to target."""
        # Calculate adaptive settings for current time
        now = datetime.now()
        adaptive_brightness = self._calculator.get_brightness_pct(now)
        adaptive_color_temp = self._calculator.get_color_temp_kelvin(now)
        
        # Apply white balance correction
        corrected_color_temp = adaptive_color_temp + self._white_balance_offset
        
        # Apply brightness factor and convert to 0-255 range
        corrected_brightness = int(adaptive_brightness * self._brightness_factor * 255 / 100)
        corrected_brightness = max(1, min(255, corrected_brightness))
        
        # Ensure color temp is in valid range
        corrected_color_temp = max(2000, min(6500, corrected_color_temp))
        
        # Override with any explicitly provided values
        final_brightness = kwargs.get(ATTR_BRIGHTNESS, corrected_brightness)
        final_color_temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN, corrected_color_temp)
        transition = kwargs.get(ATTR_TRANSITION, 1)
        
        # Update internal state
        self._is_on = True
        self._brightness = final_brightness
        self._color_temp = final_color_temp
        
        # Control the target light
        await self._control_target_light(
            turn_on=True,
            brightness=final_brightness,
            color_temp=final_color_temp,
            transition=transition
        )
        
        self.async_write_ha_state()
        
        _LOGGER.debug(
            "Turned on adaptive light %s: brightness=%d, color_temp=%d (adaptive: %d%%, %dK)",
            self._name,
            final_brightness,
            final_color_temp,
            adaptive_brightness,
            adaptive_color_temp
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the adaptive light and target light."""
        self._is_on = False
        
        transition = kwargs.get(ATTR_TRANSITION, 1)
        
        # Turn off the target light
        await self._control_target_light(
            turn_on=False,
            transition=transition
        )
        
        self.async_write_ha_state()
        
        _LOGGER.debug("Turned off adaptive light %s", self._name)

    async def _control_target_light(
        self,
        turn_on: bool,
        brightness: Optional[int] = None,
        color_temp: Optional[int] = None,
        transition: Optional[int] = None
    ) -> None:
        """Control the target light entity."""
        try:
            if turn_on:
                service_data = {
                    "entity_id": self._target_entity_id,
                }
                
                if brightness is not None:
                    service_data[ATTR_BRIGHTNESS] = brightness
                if color_temp is not None:
                    service_data[ATTR_COLOR_TEMP_KELVIN] = color_temp
                if transition is not None:
                    service_data[ATTR_TRANSITION] = transition
                
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    service_data,
                    blocking=True
                )
            else:
                service_data = {
                    "entity_id": self._target_entity_id,
                }
                
                if transition is not None:
                    service_data[ATTR_TRANSITION] = transition
                
                await self.hass.services.async_call(
                    "light",
                    "turn_off",
                    service_data,
                    blocking=True
                )
                
        except Exception as err:
            _LOGGER.error(
                "Failed to control target light %s: %s",
                self._target_entity_id,
                err
            )
            raise

    @callback
    def async_update_settings(
        self,
        white_balance_offset: Optional[int] = None,
        brightness_factor: Optional[float] = None
    ) -> None:
        """Update the adaptive light settings."""
        if white_balance_offset is not None:
            self._white_balance_offset = white_balance_offset
        if brightness_factor is not None:
            self._brightness_factor = brightness_factor
        
        _LOGGER.debug(
            "Updated settings for %s: white_balance_offset=%d, brightness_factor=%.2f",
            self._name,
            self._white_balance_offset,
            self._brightness_factor
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        return {
            "target_entity_id": self._target_entity_id,
            "white_balance_offset": self._white_balance_offset,
            "brightness_factor": self._brightness_factor,
            "adaptive_mode": "time_based",
        }
"""Light platform for Simplified Adaptive Lighting integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_KELVIN,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from .manager import AdaptiveLightingManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simplified Adaptive Lighting lights."""
    _LOGGER.debug("Setting up light platform for entry %s", config_entry.entry_id)
    
    try:
        # Get the entry data from the domain data
        entry_data = hass.data[DOMAIN][config_entry.entry_id]
        manager = entry_data["manager"]
        config_data = entry_data["config"]
        
        # Create adaptive light entities for each configured light
        lights = []
        for light_config in config_data.get("lights", []):
            entity_id = light_config["entity_id"]
            
            # Validate that the target light entity exists
            target_state = hass.states.get(entity_id)
            if not target_state:
                _LOGGER.warning("Target light entity %s not found, skipping", entity_id)
                continue
            
            # Check if it's actually a light entity
            if not entity_id.startswith("light."):
                _LOGGER.warning("Entity %s is not a light entity, skipping", entity_id)
                continue
            
            adaptive_light = AdaptiveLightEntity(
                hass=hass,
                config_entry=config_entry,
                manager=manager,
                target_entity_id=entity_id,
                light_config=light_config,
                integration_name=config_data[CONF_NAME],
            )
            lights.append(adaptive_light)
            _LOGGER.debug("Created adaptive light entity for %s", entity_id)
        
        if lights:
            async_add_entities(lights)
            _LOGGER.info("Successfully set up %d adaptive light entities", len(lights))
        else:
            _LOGGER.warning("No valid lights configured for adaptive lighting")
        
    except KeyError as err:
        _LOGGER.error("Failed to get manager from domain data: %s", err)
        raise
    except Exception as err:
        _LOGGER.error("Error setting up light platform: %s", err)
        raise


class AdaptiveLightEntity(LightEntity):
    """Adaptive light entity that wraps an existing light with time-based adjustments."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        manager: AdaptiveLightingManager,
        target_entity_id: str,
        light_config: dict[str, Any],
        integration_name: str,
    ) -> None:
        """Initialize the adaptive light entity."""
        self.hass = hass
        self._config_entry = config_entry
        self._manager = manager
        self._target_entity_id = target_entity_id
        self._light_config = light_config
        
        # Generate unique entity ID and name with proper naming scheme
        target_name = target_entity_id.split(".")[-1]
        
        # Create a more descriptive unique ID
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{target_name}"
        
        # Get the friendly name from the target entity if available
        target_state = hass.states.get(target_entity_id)
        if target_state and target_state.attributes.get("friendly_name"):
            friendly_name = target_state.attributes["friendly_name"]
            self._attr_name = f"Adaptive {friendly_name}"
        else:
            # Fallback to formatted entity name
            formatted_name = target_name.replace("_", " ").title()
            self._attr_name = f"Adaptive {formatted_name}"
        
        # Set up device info for device registry integration
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"Simplified Adaptive Lighting ({integration_name})",
            manufacturer="Simplified Adaptive Lighting",
            model="Adaptive Light Controller",
            sw_version="0.0.2",
        )
        
        # Light capabilities - HomeKit compatible
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_supported_features = (
            LightEntityFeature.TRANSITION |
            LightEntityFeature.FLASH
        )
        
        # HomeKit compatibility attributes
        self._attr_device_class = LIGHT_DOMAIN
        self._attr_entity_category = None  # Primary entity, not diagnostic/config
        
        # State tracking
        self._is_on = False
        self._brightness = None
        self._color_temp = None
        self._available = True
        self._context = Context()
        self._adaptive_enabled = True  # Adaptive functionality enabled by default
        
        # Track target light state changes
        self._unsub_state_listener = None

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()
        
        # Start tracking the target light's state
        self._unsub_state_listener = async_track_state_change_event(
            self.hass,
            [self._target_entity_id],
            self._async_target_state_changed,
        )
        
        # Initialize state from target light
        await self._async_update_from_target()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        if self._unsub_state_listener:
            self._unsub_state_listener()
            self._unsub_state_listener = None

    @callback
    async def _async_target_state_changed(self, event) -> None:
        """Handle target light state changes."""
        await self._async_update_from_target()
        self.async_write_ha_state()

    async def _async_update_from_target(self) -> None:
        """Update our state based on the target light's current state."""
        target_state = self.hass.states.get(self._target_entity_id)
        
        if not target_state or target_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._available = False
            return
        
        self._available = True
        self._is_on = target_state.state == STATE_ON
        
        if self._is_on:
            # Extract brightness and color temperature from target state
            attributes = target_state.attributes
            self._brightness = attributes.get(ATTR_BRIGHTNESS)
            
            # Handle color temperature - check both kelvin and mireds
            if ATTR_KELVIN in attributes:
                self._color_temp = attributes[ATTR_KELVIN]
            elif ATTR_COLOR_TEMP in attributes:
                # Convert mireds to kelvin if needed
                mireds = attributes[ATTR_COLOR_TEMP]
                self._color_temp = int(1000000 / mireds) if mireds > 0 else None
            else:
                self._color_temp = None
        else:
            self._brightness = None
            self._color_temp = None

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._color_temp

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        light_config = self._manager.get_light_config(self._target_entity_id)
        if light_config:
            return light_config.min_color_temp
        return 2000  # Default fallback

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        light_config = self._manager.get_light_config(self._target_entity_id)
        if light_config:
            return light_config.max_color_temp
        return 6500  # Default fallback

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the adaptive light with calculated adaptive settings."""
        if not self._available:
            return

        # Calculate adaptive settings if not overridden by user
        adaptive_kwargs = dict(kwargs)
        
        # Only apply adaptive settings if user hasn't specified them
        if not self._should_skip_adaptive_settings(kwargs):
            try:
                adaptive_settings = self._manager.calculate_adaptive_settings(self._target_entity_id)
                
                # Apply adaptive brightness if not specified by user
                if ATTR_BRIGHTNESS not in kwargs:
                    adaptive_kwargs[ATTR_BRIGHTNESS] = adaptive_settings.brightness
                
                # Apply adaptive color temperature if not specified by user
                if ATTR_COLOR_TEMP not in kwargs and ATTR_KELVIN not in kwargs:
                    adaptive_kwargs[ATTR_KELVIN] = adaptive_settings.color_temp_kelvin
                
                # Apply transition if not specified
                if ATTR_TRANSITION not in kwargs:
                    adaptive_kwargs[ATTR_TRANSITION] = adaptive_settings.transition
                    
            except Exception as err:
                _LOGGER.warning("Failed to calculate adaptive settings for %s: %s", self._target_entity_id, err)
                # Continue with original kwargs if adaptive calculation fails

        # Call the target light with adaptive settings
        await self._async_call_target_service("turn_on", **adaptive_kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the adaptive light."""
        if not self._available:
            return
        
        await self._async_call_target_service("turn_off", **kwargs)

    async def async_flash(self, **kwargs: Any) -> None:
        """Flash the adaptive light (HomeKit compatibility)."""
        if not self._available:
            return
        
        # Flash the target light
        flash_kwargs = dict(kwargs)
        flash_kwargs["flash"] = "short"  # Default to short flash
        await self._async_call_target_service("turn_on", **flash_kwargs)

    def _should_skip_adaptive_settings(self, kwargs: dict[str, Any]) -> bool:
        """
        Determine if adaptive settings should be skipped.
        
        Skip adaptive settings if:
        - Adaptive functionality is disabled
        - User has explicitly provided brightness or color temperature
        """
        return (
            not self._adaptive_enabled or
            ATTR_BRIGHTNESS in kwargs or 
            ATTR_COLOR_TEMP in kwargs or 
            ATTR_KELVIN in kwargs
        )

    async def _async_call_target_service(self, service: str, **kwargs: Any) -> None:
        """Call a service on the target light entity."""
        service_data = {
            "entity_id": self._target_entity_id,
            **kwargs
        }
        
        try:
            await self.hass.services.async_call(
                "light",
                service,
                service_data,
                blocking=True,
                context=self._context,
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to call %s service on target light %s: %s",
                service,
                self._target_entity_id,
                err
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attributes = {
            "target_entity_id": self._target_entity_id,
            "integration": DOMAIN,
            # HomeKit compatibility attributes
            "homekit_compatible": True,
            "supports_brightness": True,
            "supports_color_temperature": True,
        }
        
        # Add light-specific corrections and configuration
        corrections = self._manager.get_light_corrections(self._target_entity_id)
        attributes.update({
            "min_color_temp": corrections["min_color_temp"],
            "max_color_temp": corrections["max_color_temp"],
            "white_balance_offset": corrections["white_balance_offset"],
            "brightness_factor": corrections["brightness_factor"],
            "enabled": corrections["enabled"],
        })
        
        # Add adaptive functionality status
        attributes["adaptive_enabled"] = self._adaptive_enabled
        
        # Add current adaptive settings if available and enabled
        if self._adaptive_enabled:
            try:
                adaptive_settings = self._manager.calculate_adaptive_settings(self._target_entity_id)
                attributes.update({
                    "adaptive_brightness": adaptive_settings.brightness,
                    "adaptive_color_temp": adaptive_settings.color_temp_kelvin,
                })
            except Exception as err:
                # Don't fail if adaptive calculation fails, but log it
                _LOGGER.debug("Could not calculate adaptive settings for %s: %s", self._target_entity_id, err)
        
        return attributes

    @property
    def is_adaptive_enabled(self) -> bool:
        """Return whether adaptive functionality is enabled."""
        return self._adaptive_enabled

    async def async_enable_adaptive(self) -> None:
        """Enable adaptive functionality for this light."""
        if not self._adaptive_enabled:
            self._adaptive_enabled = True
            self.async_write_ha_state()
            _LOGGER.debug("Enabled adaptive functionality for %s", self.entity_id)

    async def async_disable_adaptive(self) -> None:
        """Disable adaptive functionality for this light."""
        if self._adaptive_enabled:
            self._adaptive_enabled = False
            self.async_write_ha_state()
            _LOGGER.debug("Disabled adaptive functionality for %s", self.entity_id)

    def set_adaptive_enabled(self, enabled: bool) -> None:
        """Set adaptive functionality enabled state (synchronous version)."""
        if self._adaptive_enabled != enabled:
            self._adaptive_enabled = enabled
            self.async_write_ha_state()
            _LOGGER.debug("%s adaptive functionality for %s", 
                         "Enabled" if enabled else "Disabled", self.entity_id)
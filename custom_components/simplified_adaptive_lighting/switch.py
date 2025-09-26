"""Switch platform for Simplified Adaptive Lighting integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .manager import AdaptiveLightingManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simplified Adaptive Lighting switch."""
    _LOGGER.debug("Setting up switch platform for entry %s", config_entry.entry_id)
    
    try:
        # Get the entry data from the domain data
        entry_data = hass.data[DOMAIN][config_entry.entry_id]
        manager = entry_data["manager"]
        config_data = entry_data["config"]
        
        # Create switch for controlling adaptive lighting
        switch = AdaptiveLightingSwitch(
            hass=hass,
            config_entry=config_entry,
            manager=manager,
            name=config_data[CONF_NAME],
            unique_id=config_entry.entry_id,
        )
        
        async_add_entities([switch])
        _LOGGER.debug("Successfully set up switch platform")
        
    except KeyError as err:
        _LOGGER.error("Failed to get manager from domain data: %s", err)
        raise
    except Exception as err:
        _LOGGER.error("Error setting up switch platform: %s", err)
        raise


class AdaptiveLightingSwitch(SwitchEntity, RestoreEntity):
    """Switch entity for controlling adaptive lighting system."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        manager: AdaptiveLightingManager,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize the adaptive lighting switch."""
        self.hass = hass
        self._config_entry = config_entry
        self._manager = manager
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:lightbulb-auto"
        self._is_on = False
        
        # Set up device info for device registry integration
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"Simplified Adaptive Lighting ({name})",
            manufacturer="Simplified Adaptive Lighting",
            model="Adaptive Lighting Controller",
            sw_version="1.0.0",
            configuration_url=None,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
            
            # If the switch was on before restart, re-enable interception
            if self._is_on:
                try:
                    await self._manager.enable_interception()
                    _LOGGER.debug("Restored adaptive lighting state: enabled")
                except Exception as err:
                    _LOGGER.error("Failed to restore adaptive lighting state: %s", err)
                    self._is_on = False
        
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if adaptive lighting is enabled."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        lights_config = self._config_entry.data.get("lights", [])
        return {
            "adaptive_lights_count": len(lights_config),
            "configured_lights": [light["entity_id"] for light in lights_config],
            "interception_enabled": self._manager.is_interception_enabled,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable adaptive lighting by starting service call interception."""
        try:
            await self._manager.enable_interception()
            
            # Verify interception was actually enabled
            if self._manager.is_interception_enabled:
                self._is_on = True
                _LOGGER.debug("Adaptive lighting enabled successfully")
            else:
                self._is_on = False
                _LOGGER.warning("Adaptive lighting failed to enable - interception not active")
                
        except Exception as err:
            _LOGGER.error("Failed to enable adaptive lighting: %s", err)
            # Fallback to disabled state on any setup failure
            self._is_on = False
            try:
                # Ensure clean state by attempting to disable interception
                await self._manager.disable_interception()
            except Exception as cleanup_err:
                _LOGGER.error("Failed to cleanup after enable failure: %s", cleanup_err)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable adaptive lighting by stopping service call interception."""
        try:
            await self._manager.disable_interception()
            
            # Verify interception was actually disabled
            if not self._manager.is_interception_enabled:
                self._is_on = False
                _LOGGER.debug("Adaptive lighting disabled successfully")
            else:
                # Keep current state if disable failed
                _LOGGER.warning("Adaptive lighting failed to disable - interception still active")
                
        except Exception as err:
            _LOGGER.error("Failed to disable adaptive lighting: %s", err)
            # Always reflect the actual manager state
            self._is_on = self._manager.is_interception_enabled
        
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        # Ensure service call interception is properly cleaned up
        if self._is_on:
            try:
                await self._manager.disable_interception()
                _LOGGER.debug("Cleaned up service call interception on entity removal")
            except Exception as err:
                _LOGGER.error("Failed to cleanup service call interception: %s", err)
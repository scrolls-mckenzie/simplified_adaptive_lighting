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
            
            # If the switch was on before restart, re-enable adaptive lighting
            if self._is_on:
                try:
                    await self._enable_adaptive_lights()
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
        
        # Get adaptive light entity states
        adaptive_light_states = self._get_adaptive_light_states()
        
        return {
            "adaptive_lights_count": len(lights_config),
            "configured_lights": [light["entity_id"] for light in lights_config],
            "adaptive_lights_enabled": adaptive_light_states["enabled_count"],
            "adaptive_lights_on": adaptive_light_states["on_count"],
            "adaptive_lights_available": adaptive_light_states["available_count"],
            "interception_enabled": self._manager.is_interception_enabled,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable adaptive lighting by enabling all adaptive light entities."""
        try:
            # Enable adaptive functionality on all adaptive light entities
            await self._enable_adaptive_lights()
            
            # Also enable service call interception for backward compatibility
            await self._manager.enable_interception()
            
            # Verify at least one method was enabled
            if self._manager.is_interception_enabled or self._get_adaptive_light_states()["enabled_count"] > 0:
                self._is_on = True
                _LOGGER.debug("Adaptive lighting enabled successfully")
            else:
                self._is_on = False
                _LOGGER.warning("Adaptive lighting failed to enable - no adaptive lights or interception active")
                
        except Exception as err:
            _LOGGER.error("Failed to enable adaptive lighting: %s", err)
            # Fallback to disabled state on any setup failure
            self._is_on = False
            try:
                # Ensure clean state by attempting to disable both methods
                await self._disable_adaptive_lights()
                await self._manager.disable_interception()
            except Exception as cleanup_err:
                _LOGGER.error("Failed to cleanup after enable failure: %s", cleanup_err)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable adaptive lighting by disabling all adaptive light entities."""
        try:
            # Disable adaptive functionality on all adaptive light entities
            await self._disable_adaptive_lights()
            
            # Also disable service call interception
            await self._manager.disable_interception()
            
            # Verify both methods were disabled
            if not self._manager.is_interception_enabled and self._get_adaptive_light_states()["enabled_count"] == 0:
                self._is_on = False
                _LOGGER.debug("Adaptive lighting disabled successfully")
            else:
                # Keep current state if disable failed
                _LOGGER.warning("Adaptive lighting failed to disable - some adaptive lights or interception still active")
                
        except Exception as err:
            _LOGGER.error("Failed to disable adaptive lighting: %s", err)
            # Always reflect the actual state
            self._is_on = (
                self._manager.is_interception_enabled or 
                self._get_adaptive_light_states()["enabled_count"] > 0
            )
        
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        # Ensure adaptive lighting is properly cleaned up
        if self._is_on:
            try:
                await self._disable_adaptive_lights()
                await self._manager.disable_interception()
                _LOGGER.debug("Cleaned up adaptive lighting on entity removal")
            except Exception as err:
                _LOGGER.error("Failed to cleanup adaptive lighting: %s", err)

    async def _enable_adaptive_lights(self) -> None:
        """Enable adaptive functionality on all adaptive light entities."""
        adaptive_light_entities = self._get_adaptive_light_entities()
        
        for entity in adaptive_light_entities:
            try:
                # Enable adaptive functionality on the entity
                if hasattr(entity, 'async_enable_adaptive'):
                    await entity.async_enable_adaptive()
                elif hasattr(entity, 'set_adaptive_enabled'):
                    entity.set_adaptive_enabled(True)
                _LOGGER.debug("Enabled adaptive functionality for %s", entity.entity_id)
            except Exception as err:
                _LOGGER.warning("Failed to enable adaptive functionality for %s: %s", entity.entity_id, err)

    async def _disable_adaptive_lights(self) -> None:
        """Disable adaptive functionality on all adaptive light entities."""
        adaptive_light_entities = self._get_adaptive_light_entities()
        
        for entity in adaptive_light_entities:
            try:
                # Disable adaptive functionality on the entity
                if hasattr(entity, 'async_disable_adaptive'):
                    await entity.async_disable_adaptive()
                elif hasattr(entity, 'set_adaptive_enabled'):
                    entity.set_adaptive_enabled(False)
                _LOGGER.debug("Disabled adaptive functionality for %s", entity.entity_id)
            except Exception as err:
                _LOGGER.warning("Failed to disable adaptive functionality for %s: %s", entity.entity_id, err)

    def _get_adaptive_light_entities(self) -> list:
        """Get all adaptive light entities for this integration."""
        adaptive_entities = []
        
        try:
            # Look for adaptive light entities in the entity registry
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            
            for entity_id, entry in entity_registry.entities.items():
                if (entry.config_entry_id == self._config_entry.entry_id and 
                    entity_id.startswith("light.") and 
                    entry.platform == DOMAIN):
                    
                    # Get the actual entity object from the light platform
                    light_component = self.hass.data.get("entity_components", {}).get("light")
                    if light_component:
                        entity_obj = light_component.get_entity(entity_id)
                        if entity_obj:
                            adaptive_entities.append(entity_obj)
        except Exception as err:
            _LOGGER.warning("Failed to get adaptive light entities: %s", err)
        
        return adaptive_entities

    def _get_adaptive_light_states(self) -> dict[str, int]:
        """Get status information about adaptive light entities."""
        adaptive_entities = self._get_adaptive_light_entities()
        
        enabled_count = 0
        on_count = 0
        available_count = 0
        
        for entity in adaptive_entities:
            if hasattr(entity, 'available') and entity.available:
                available_count += 1
                
                if hasattr(entity, 'is_on') and entity.is_on:
                    on_count += 1
                
                # Check if adaptive functionality is enabled
                if (hasattr(entity, 'is_adaptive_enabled') and entity.is_adaptive_enabled) or \
                   (hasattr(entity, '_adaptive_enabled') and entity._adaptive_enabled):
                    enabled_count += 1
        
        return {
            "enabled_count": enabled_count,
            "on_count": on_count,
            "available_count": available_count,
            "total_count": len(adaptive_entities),
        }
"""Simplified Adaptive Lighting integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .manager import AdaptiveLightingManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Simplified Adaptive Lighting integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Simplified Adaptive Lighting from a config entry."""
    _LOGGER.debug("Setting up Simplified Adaptive Lighting integration for entry %s", entry.entry_id)
    
    try:
        # Initialize the data storage for this domain
        hass.data.setdefault(DOMAIN, {})
        
        # Create the adaptive lighting manager
        manager = AdaptiveLightingManager(hass, entry.data)
        
        # Set up the manager
        setup_success = await manager.setup()
        if not setup_success:
            _LOGGER.error("Failed to set up adaptive lighting manager")
            return False
        
        # Store the manager and config data for platforms to access
        hass.data[DOMAIN][entry.entry_id] = {
            "manager": manager,
            "config": entry.data,
        }
        
        # Register services
        await _async_register_services(hass)
        
        # Set up platforms (switch only - we intercept light calls, don't create light entities)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        _LOGGER.info("Successfully set up Simplified Adaptive Lighting integration")
        return True
        
    except Exception as err:
        _LOGGER.error("Error setting up Simplified Adaptive Lighting integration: %s", err)
        # Clean up any partial setup
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(f"Failed to set up integration: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Simplified Adaptive Lighting integration for entry %s", entry.entry_id)
    
    try:
        # Get the manager for cleanup
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        manager = entry_data.get("manager")
        
        # Disable service interception before unloading
        if manager:
            await manager.disable_interception()
            _LOGGER.debug("Disabled service interception for entry %s", entry.entry_id)
        
        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            # Clean up stored data
            hass.data[DOMAIN].pop(entry.entry_id, None)
            
            # Unregister services if this is the last entry
            if not hass.data[DOMAIN]:
                _async_unregister_services(hass)
            
            _LOGGER.info("Successfully unloaded Simplified Adaptive Lighting integration")
        else:
            _LOGGER.error("Failed to unload platforms for entry %s", entry.entry_id)
        
        return unload_ok
        
    except Exception as err:
        _LOGGER.error("Error unloading Simplified Adaptive Lighting integration: %s", err)
        # Still try to clean up data even if there was an error
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)
        return False


# Service schemas
SERVICE_APPLY_ADAPTIVE_SETTINGS = "apply_adaptive_settings"
SERVICE_ENABLE_ADAPTIVE_LIGHTING = "enable_adaptive_lighting"
SERVICE_DISABLE_ADAPTIVE_LIGHTING = "disable_adaptive_lighting"

APPLY_ADAPTIVE_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("lights"): cv.entity_ids,
        vol.Optional("transition", default=1): vol.All(vol.Coerce(float), vol.Range(min=0, max=300)),
    }
)

ENABLE_DISABLE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register services for the integration."""
    # Only register services once
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_ADAPTIVE_SETTINGS):
        return
    
    async def async_apply_adaptive_settings(call: ServiceCall) -> None:
        """Handle apply_adaptive_settings service call."""
        switch_entity_id = call.data["entity_id"]
        lights = call.data.get("lights", [])
        transition = call.data.get("transition", 1)
        
        # Find the manager for this switch
        manager = None
        for entry_data in hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "manager" in entry_data:
                # This is a simple check - in a real implementation you'd want to 
                # match the switch entity_id to the correct manager
                manager = entry_data["manager"]
                break
        
        if not manager:
            raise ServiceValidationError(f"No adaptive lighting manager found for {switch_entity_id}")
        
        # If no lights specified, use all configured lights
        if not lights:
            lights = manager.configured_lights
        
        # Apply adaptive settings to each light
        for light_entity_id in lights:
            if light_entity_id in manager.configured_lights:
                adaptive_settings = manager.calculate_adaptive_settings(light_entity_id)
                
                # Call light.turn_on with adaptive settings
                service_data = {
                    "entity_id": light_entity_id,
                    "transition": transition,
                }
                service_data.update(adaptive_settings.to_service_data())
                
                await hass.services.async_call(
                    "light",
                    "turn_on",
                    service_data,
                    context=call.context,
                )
    
    async def async_enable_adaptive_lighting(call: ServiceCall) -> None:
        """Handle enable_adaptive_lighting service call."""
        switch_entity_id = call.data["entity_id"]
        
        # Find and enable the switch
        switch_entity = hass.states.get(switch_entity_id)
        if not switch_entity:
            raise ServiceValidationError(f"Switch entity {switch_entity_id} not found")
        
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": switch_entity_id},
            context=call.context,
        )
    
    async def async_disable_adaptive_lighting(call: ServiceCall) -> None:
        """Handle disable_adaptive_lighting service call."""
        switch_entity_id = call.data["entity_id"]
        
        # Find and disable the switch
        switch_entity = hass.states.get(switch_entity_id)
        if not switch_entity:
            raise ServiceValidationError(f"Switch entity {switch_entity_id} not found")
        
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": switch_entity_id},
            context=call.context,
        )
    
    # Register the services
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_ADAPTIVE_SETTINGS,
        async_apply_adaptive_settings,
        schema=APPLY_ADAPTIVE_SETTINGS_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE_ADAPTIVE_LIGHTING,
        async_enable_adaptive_lighting,
        schema=ENABLE_DISABLE_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_ADAPTIVE_LIGHTING,
        async_disable_adaptive_lighting,
        schema=ENABLE_DISABLE_SCHEMA,
    )
    
    _LOGGER.debug("Registered services for %s", DOMAIN)


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services for the integration."""
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_ADAPTIVE_SETTINGS):
        hass.services.async_remove(DOMAIN, SERVICE_APPLY_ADAPTIVE_SETTINGS)
    
    if hass.services.has_service(DOMAIN, SERVICE_ENABLE_ADAPTIVE_LIGHTING):
        hass.services.async_remove(DOMAIN, SERVICE_ENABLE_ADAPTIVE_LIGHTING)
    
    if hass.services.has_service(DOMAIN, SERVICE_DISABLE_ADAPTIVE_LIGHTING):
        hass.services.async_remove(DOMAIN, SERVICE_DISABLE_ADAPTIVE_LIGHTING)
    
    _LOGGER.debug("Unregistered services for %s", DOMAIN)
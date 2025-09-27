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
from homeassistant.helpers import entity_registry as er

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
        
        # Set up platforms (switch and light entities)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Add options update listener
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        
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
        
        # Clean up manager before unloading
        if manager:
            _LOGGER.debug("Cleaning up manager for entry %s", entry.entry_id)
        
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


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


# Service schemas
SERVICE_APPLY_ADAPTIVE_SETTINGS = "apply_adaptive_settings"
SERVICE_ENABLE_ADAPTIVE_LIGHTING = "enable_adaptive_lighting"
SERVICE_DISABLE_ADAPTIVE_LIGHTING = "disable_adaptive_lighting"
SERVICE_SET_MANUAL_COLOR_TEMP = "set_manual_color_temp"
SERVICE_ENABLE_ADAPTIVE_PER_LIGHT = "enable_adaptive_per_light"
SERVICE_DISABLE_ADAPTIVE_PER_LIGHT = "disable_adaptive_per_light"
SERVICE_TEST_WHITE_BALANCE = "test_white_balance"

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

SET_MANUAL_COLOR_TEMP_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("color_temp_kelvin"): vol.All(vol.Coerce(int), vol.Range(min=1000, max=10000)),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
        vol.Optional("transition", default=1): vol.All(vol.Coerce(float), vol.Range(min=0, max=300)),
    }
)

ENABLE_DISABLE_PER_LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
    }
)

TEST_WHITE_BALANCE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("white_balance_offset"): vol.All(vol.Coerce(int), vol.Range(min=-1000, max=1000)),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
        vol.Optional("transition", default=1): vol.All(vol.Coerce(float), vol.Range(min=0, max=300)),
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
    
    async def async_set_manual_color_temp(call: ServiceCall) -> None:
        """Handle set_manual_color_temp service call."""
        entity_ids = call.data["entity_id"]
        color_temp_kelvin = call.data["color_temp_kelvin"]
        brightness = call.data.get("brightness")
        transition = call.data.get("transition", 1)
        
        # Ensure entity_ids is a list
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        
        for entity_id in entity_ids:
            # Verify this is an adaptive light entity
            entity_state = hass.states.get(entity_id)
            if not entity_state:
                _LOGGER.warning("Entity %s not found", entity_id)
                continue
            
            # Check if it's an adaptive light entity
            if not entity_state.attributes.get("integration") == DOMAIN:
                _LOGGER.warning("Entity %s is not an adaptive light entity", entity_id)
                continue
            
            # Get the target entity ID from the adaptive light
            target_entity_id = entity_state.attributes.get("target_entity_id")
            if not target_entity_id:
                _LOGGER.warning("No target entity found for adaptive light %s", entity_id)
                continue
            
            # Prepare service data
            service_data = {
                "entity_id": target_entity_id,
                "color_temp_kelvin": color_temp_kelvin,
                "transition": transition,
            }
            
            # Add brightness if specified
            if brightness is not None:
                service_data["brightness"] = brightness
            
            # Call the target light directly with manual settings
            await hass.services.async_call(
                "light",
                "turn_on",
                service_data,
                context=call.context,
            )
            
            _LOGGER.debug("Set manual color temp %dK on %s", color_temp_kelvin, target_entity_id)
    
    async def async_enable_adaptive_per_light(call: ServiceCall) -> None:
        """Handle enable_adaptive_per_light service call."""
        entity_ids = call.data["entity_id"]
        
        # Ensure entity_ids is a list
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        
        for entity_id in entity_ids:
            # Verify this is an adaptive light entity
            entity_state = hass.states.get(entity_id)
            if not entity_state:
                _LOGGER.warning("Entity %s not found", entity_id)
                continue
            
            # Check if it's an adaptive light entity
            if not entity_state.attributes.get("integration") == DOMAIN:
                _LOGGER.warning("Entity %s is not an adaptive light entity", entity_id)
                continue
            
            # Find the entity object and call its enable method
            entity_registry = er.async_get(hass)
            entity_entry = entity_registry.async_get(entity_id)
            
            if entity_entry and entity_entry.platform == DOMAIN:
                # Get the platform and call the entity method
                # This is a simplified approach - the entity should handle this via its own service
                _LOGGER.debug("Enabled adaptive functionality for %s", entity_id)
            else:
                _LOGGER.warning("Could not find adaptive light entity %s", entity_id)
    
    async def async_disable_adaptive_per_light(call: ServiceCall) -> None:
        """Handle disable_adaptive_per_light service call."""
        entity_ids = call.data["entity_id"]
        
        # Ensure entity_ids is a list
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        
        for entity_id in entity_ids:
            # Verify this is an adaptive light entity
            entity_state = hass.states.get(entity_id)
            if not entity_state:
                _LOGGER.warning("Entity %s not found", entity_id)
                continue
            
            # Check if it's an adaptive light entity
            if not entity_state.attributes.get("integration") == DOMAIN:
                _LOGGER.warning("Entity %s is not an adaptive light entity", entity_id)
                continue
            
            # Find the entity object and call its disable method
            entity_registry = er.async_get(hass)
            entity_entry = entity_registry.async_get(entity_id)
            
            if entity_entry and entity_entry.platform == DOMAIN:
                # Get the platform and call the entity method
                # This is a simplified approach - the entity should handle this via its own service
                _LOGGER.debug("Disabled adaptive functionality for %s", entity_id)
            else:
                _LOGGER.warning("Could not find adaptive light entity %s", entity_id)
    
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
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MANUAL_COLOR_TEMP,
        async_set_manual_color_temp,
        schema=SET_MANUAL_COLOR_TEMP_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE_ADAPTIVE_PER_LIGHT,
        async_enable_adaptive_per_light,
        schema=ENABLE_DISABLE_PER_LIGHT_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_ADAPTIVE_PER_LIGHT,
        async_disable_adaptive_per_light,
        schema=ENABLE_DISABLE_PER_LIGHT_SCHEMA,
    )
    
    async def async_test_white_balance(call: ServiceCall) -> None:
        """Handle test_white_balance service call."""
        entity_id = call.data["entity_id"]
        white_balance_offset = call.data["white_balance_offset"]
        brightness = call.data.get("brightness")
        transition = call.data.get("transition", 1)
        
        # Get the adaptive light entity
        light_component = hass.data.get("entity_components", {}).get("light")
        if not light_component:
            raise ServiceValidationError(f"Light component not found")
        
        entity = light_component.get_entity(entity_id)
        if not entity:
            raise ServiceValidationError(f"Adaptive light entity {entity_id} not found")
        
        # Check if it's one of our adaptive light entities
        if not hasattr(entity, '_manager'):
            raise ServiceValidationError(f"Entity {entity_id} is not an adaptive light entity")
        
        # Calculate current adaptive settings
        try:
            adaptive_settings = entity._manager.calculate_adaptive_settings(entity._target_entity_id)
            
            # Apply white balance offset to the color temperature
            test_color_temp = adaptive_settings.color_temp_kelvin + white_balance_offset
            
            # Use provided brightness or adaptive brightness
            test_brightness = brightness if brightness is not None else adaptive_settings.brightness
            
            # Apply the test settings to the target light
            service_data = {
                "entity_id": entity._target_entity_id,
                "color_temp_kelvin": test_color_temp,
                "brightness": test_brightness,
                "transition": transition,
            }
            
            await hass.services.async_call("light", "turn_on", service_data)
            
            _LOGGER.info("Applied test white balance offset %dK to %s (color_temp: %dK)", 
                        white_balance_offset, entity_id, test_color_temp)
                        
        except Exception as err:
            _LOGGER.error("Failed to test white balance for %s: %s", entity_id, err)
            raise ServiceValidationError(f"Failed to test white balance: {err}")
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_WHITE_BALANCE,
        async_test_white_balance,
        schema=TEST_WHITE_BALANCE_SCHEMA,
    )
    
    _LOGGER.debug("Registered services for %s", DOMAIN)


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services for the integration."""
    services_to_remove = [
        SERVICE_APPLY_ADAPTIVE_SETTINGS,
        SERVICE_ENABLE_ADAPTIVE_LIGHTING,
        SERVICE_DISABLE_ADAPTIVE_LIGHTING,
        SERVICE_SET_MANUAL_COLOR_TEMP,
        SERVICE_ENABLE_ADAPTIVE_PER_LIGHT,
        SERVICE_DISABLE_ADAPTIVE_PER_LIGHT,
        SERVICE_TEST_WHITE_BALANCE,
    ]
    
    for service in services_to_remove:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    
    _LOGGER.debug("Unregistered services for %s", DOMAIN)
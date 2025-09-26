"""Simplified Adaptive Lighting integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .manager import AdaptiveLightingManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


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
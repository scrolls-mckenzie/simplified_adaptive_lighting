"""Light platform for Simplified Adaptive Lighting integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .adaptive_light import AdaptiveLight

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simplified Adaptive Lighting lights."""
    config_data = config_entry.data
    lights_config = config_data.get("lights", [])
    
    # Create adaptive light entities for each configured light
    adaptive_lights = []
    for light_config in lights_config:
        adaptive_light = AdaptiveLight(
            hass=hass,
            target_entity_id=light_config["entity_id"],
            name=f"Adaptive {light_config.get('name', light_config['entity_id'])}",
            white_balance_offset=light_config.get("white_balance_offset", 0),
            brightness_factor=light_config.get("brightness_factor", 1.0),
        )
        adaptive_lights.append(adaptive_light)
    
    async_add_entities(adaptive_lights)
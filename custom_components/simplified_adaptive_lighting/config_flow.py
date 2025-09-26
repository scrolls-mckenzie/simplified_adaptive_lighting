"""Config flow for Simplified Adaptive Lighting integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_BRIGHTNESS_FACTOR,
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_COLOR_TEMP,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP,
    CONF_WHITE_BALANCE_OFFSET,
    DEFAULT_BRIGHTNESS_FACTOR,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MAX_COLOR_TEMP,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_MIN_COLOR_TEMP,
    DEFAULT_WHITE_BALANCE_OFFSET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SimplifiedAdaptiveLightingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Simplified Adaptive Lighting."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}
        self._selected_lights: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input
            name = user_input[CONF_NAME]
            
            # Check if already configured
            await self.async_set_unique_id(name)
            self._abort_if_unique_id_configured()
            
            # Store basic config and proceed to light selection
            self._config.update(user_input)
            return await self.async_step_select_lights()

        # Show the initial configuration form
        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default="Adaptive Lighting"): str,
            vol.Optional(CONF_MIN_BRIGHTNESS, default=DEFAULT_MIN_BRIGHTNESS): vol.Range(min=1, max=255),
            vol.Optional(CONF_MAX_BRIGHTNESS, default=DEFAULT_MAX_BRIGHTNESS): vol.Range(min=1, max=255),
            vol.Optional(CONF_MIN_COLOR_TEMP, default=DEFAULT_MIN_COLOR_TEMP): vol.Range(min=1000, max=10000),
            vol.Optional(CONF_MAX_COLOR_TEMP, default=DEFAULT_MAX_COLOR_TEMP): vol.Range(min=1000, max=10000),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle light selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_lights = user_input.get("lights", [])
            
            if not selected_lights:
                errors["lights"] = "no_lights_selected"
            else:
                self._selected_lights = selected_lights
                return await self.async_step_configure_lights()

        # Get available light entities
        light_entities = self._get_light_entities()
        
        if not light_entities:
            return self.async_abort(reason="no_lights_available")

        data_schema = vol.Schema({
            vol.Required("lights"): cv.multi_select(light_entities),
        })

        return self.async_show_form(
            step_id="select_lights",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_configure_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle per-light configuration step."""
        if user_input is not None:
            # Process light configurations
            lights_config = []
            
            for entity_id in self._selected_lights:
                light_config = {
                    "entity_id": entity_id,
                    CONF_WHITE_BALANCE_OFFSET: user_input.get(f"{entity_id}_white_balance", DEFAULT_WHITE_BALANCE_OFFSET),
                    CONF_BRIGHTNESS_FACTOR: user_input.get(f"{entity_id}_brightness_factor", DEFAULT_BRIGHTNESS_FACTOR),
                }
                lights_config.append(light_config)
            
            # Combine all configuration
            final_config = {
                **self._config,
                CONF_LIGHTS: lights_config,
            }
            
            return self.async_create_entry(
                title=self._config[CONF_NAME],
                data=final_config,
            )

        # Create schema for per-light configuration
        schema_dict = {}
        
        for entity_id in self._selected_lights:
            entity_name = self._get_entity_name(entity_id)
            schema_dict[vol.Optional(f"{entity_id}_white_balance", default=DEFAULT_WHITE_BALANCE_OFFSET)] = vol.Range(min=-1000, max=1000)
            schema_dict[vol.Optional(f"{entity_id}_brightness_factor", default=DEFAULT_BRIGHTNESS_FACTOR)] = vol.Range(min=0.1, max=2.0)

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="configure_lights",
            data_schema=data_schema,
        )

    def _get_light_entities(self) -> dict[str, str]:
        """Get available light entities."""
        light_entities = {}
        
        # Get all light entities from the registry
        for entity in self.hass.states.async_all():
            entity_id = entity.entity_id
            if entity_id.startswith("light.") and entity.state != "unavailable":
                # Check if the light supports brightness and color temperature
                attributes = entity.attributes
                if (
                    "brightness" in attributes.get("supported_features", []) or
                    attributes.get("supported_color_modes") and 
                    any(mode in ["color_temp", "hs", "rgb", "rgbw", "rgbww"] 
                        for mode in attributes.get("supported_color_modes", []))
                ):
                    friendly_name = attributes.get("friendly_name", entity_id)
                    light_entities[entity_id] = friendly_name
        
        return light_entities

    def _get_entity_name(self, entity_id: str) -> str:
        """Get friendly name for an entity."""
        state = self.hass.states.get(entity_id)
        if state and state.attributes.get("friendly_name"):
            return state.attributes["friendly_name"]
        return entity_id.replace("light.", "").replace("_", " ").title()
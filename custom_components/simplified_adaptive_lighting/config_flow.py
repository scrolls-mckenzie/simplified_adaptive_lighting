"""Config flow for Simplified Adaptive Lighting integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
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
                    "min_color_temp": user_input.get(f"{entity_id}_min_color_temp", DEFAULT_MIN_COLOR_TEMP),
                    "max_color_temp": user_input.get(f"{entity_id}_max_color_temp", DEFAULT_MAX_COLOR_TEMP),
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
            # Add per-light color temperature range configuration
            schema_dict[vol.Optional(f"{entity_id}_min_color_temp", default=DEFAULT_MIN_COLOR_TEMP)] = vol.Range(min=1000, max=10000)
            schema_dict[vol.Optional(f"{entity_id}_max_color_temp", default=DEFAULT_MAX_COLOR_TEMP)] = vol.Range(min=1000, max=10000)
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
                # Check if the light supports color modes we care about
                attributes = entity.attributes
                supported_color_modes = attributes.get("supported_color_modes", [])
                if supported_color_modes:
                    # Accept any light with color modes - they all support brightness
                    friendly_name = attributes.get("friendly_name", entity_id)
                    light_entities[entity_id] = friendly_name
        
        return light_entities

    def _get_entity_name(self, entity_id: str) -> str:
        """Get friendly name for an entity."""
        state = self.hass.states.get(entity_id)
        if state and state.attributes.get("friendly_name"):
            return state.attributes["friendly_name"]
        return entity_id.replace("light.", "").replace("_", " ").title()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

class
 OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Simplified Adaptive Lighting."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._selected_light: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_main_menu()

    async def async_step_main_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show main options menu."""
        if user_input is not None:
            if user_input["action"] == "configure_light":
                return await self.async_step_select_light_to_configure()
            elif user_input["action"] == "add_lights":
                return await self.async_step_add_lights()
            elif user_input["action"] == "remove_lights":
                return await self.async_step_remove_lights()
            elif user_input["action"] == "global_settings":
                return await self.async_step_global_settings()

        # Get current configuration info
        lights_config = self.config_entry.data.get(CONF_LIGHTS, [])
        configured_lights = [light["entity_id"] for light in lights_config]

        return self.async_show_menu(
            step_id="main_menu",
            menu_options=[
                "configure_light",
                "add_lights", 
                "remove_lights",
                "global_settings"
            ],
            description_placeholders={
                "configured_count": str(len(configured_lights)),
                "configured_lights": ", ".join([self._get_entity_name(light) for light in configured_lights[:3]]) + 
                                   (f" and {len(configured_lights) - 3} more" if len(configured_lights) > 3 else "")
            }
        )

    async def async_step_select_light_to_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which light to configure."""
        if user_input is not None:
            self._selected_light = user_input["light"]
            return await self.async_step_configure_selected_light()

        # Get currently configured lights
        lights_config = self.config_entry.data.get(CONF_LIGHTS, [])
        if not lights_config:
            return self.async_abort(reason="no_lights_configured")

        # Create options for configured lights
        light_options = {}
        for light_config in lights_config:
            entity_id = light_config["entity_id"]
            friendly_name = self._get_entity_name(entity_id)
            light_options[entity_id] = friendly_name

        data_schema = vol.Schema({
            vol.Required("light"): vol.In(light_options),
        })

        return self.async_show_form(
            step_id="select_light_to_configure",
            data_schema=data_schema,
        )

    async def async_step_configure_selected_light(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the selected light."""
        if user_input is not None:
            # Update the configuration for the selected light
            new_data = dict(self.config_entry.data)
            lights_config = list(new_data.get(CONF_LIGHTS, []))
            
            # Find and update the light configuration
            for i, light_config in enumerate(lights_config):
                if light_config["entity_id"] == self._selected_light:
                    lights_config[i] = {
                        "entity_id": self._selected_light,
                        "min_color_temp": user_input["min_color_temp"],
                        "max_color_temp": user_input["max_color_temp"],
                        CONF_WHITE_BALANCE_OFFSET: user_input["white_balance_offset"],
                        CONF_BRIGHTNESS_FACTOR: user_input["brightness_factor"],
                    }
                    break
            
            new_data[CONF_LIGHTS] = lights_config
            
            return self.async_create_entry(title="", data=new_data)

        # Get current configuration for the selected light
        current_config = None
        for light_config in self.config_entry.data.get(CONF_LIGHTS, []):
            if light_config["entity_id"] == self._selected_light:
                current_config = light_config
                break

        if not current_config:
            return self.async_abort(reason="light_not_found")

        friendly_name = self._get_entity_name(self._selected_light)

        data_schema = vol.Schema({
            vol.Required(
                "min_color_temp", 
                default=current_config.get("min_color_temp", DEFAULT_MIN_COLOR_TEMP)
            ): vol.Range(min=1000, max=10000),
            vol.Required(
                "max_color_temp", 
                default=current_config.get("max_color_temp", DEFAULT_MAX_COLOR_TEMP)
            ): vol.Range(min=1000, max=10000),
            vol.Required(
                "white_balance_offset", 
                default=current_config.get(CONF_WHITE_BALANCE_OFFSET, DEFAULT_WHITE_BALANCE_OFFSET)
            ): vol.Range(min=-1000, max=1000),
            vol.Required(
                "brightness_factor", 
                default=current_config.get(CONF_BRIGHTNESS_FACTOR, DEFAULT_BRIGHTNESS_FACTOR)
            ): vol.Range(min=0.1, max=2.0),
        })

        return self.async_show_form(
            step_id="configure_selected_light",
            data_schema=data_schema,
            description_placeholders={"light_name": friendly_name},
        )

    async def async_step_add_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add new lights to the configuration."""
        if user_input is not None:
            selected_lights = user_input.get("lights", [])
            
            if not selected_lights:
                return self.async_show_form(
                    step_id="add_lights",
                    data_schema=self._get_add_lights_schema(),
                    errors={"lights": "no_lights_selected"},
                )
            
            # Add new lights with default configuration
            new_data = dict(self.config_entry.data)
            lights_config = list(new_data.get(CONF_LIGHTS, []))
            
            for entity_id in selected_lights:
                # Check if light is already configured
                if any(light["entity_id"] == entity_id for light in lights_config):
                    continue
                    
                lights_config.append({
                    "entity_id": entity_id,
                    "min_color_temp": DEFAULT_MIN_COLOR_TEMP,
                    "max_color_temp": DEFAULT_MAX_COLOR_TEMP,
                    CONF_WHITE_BALANCE_OFFSET: DEFAULT_WHITE_BALANCE_OFFSET,
                    CONF_BRIGHTNESS_FACTOR: DEFAULT_BRIGHTNESS_FACTOR,
                })
            
            new_data[CONF_LIGHTS] = lights_config
            
            return self.async_create_entry(title="", data=new_data)

        return self.async_show_form(
            step_id="add_lights",
            data_schema=self._get_add_lights_schema(),
        )

    async def async_step_remove_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove lights from the configuration."""
        if user_input is not None:
            lights_to_remove = user_input.get("lights", [])
            
            if lights_to_remove:
                # Remove selected lights
                new_data = dict(self.config_entry.data)
                lights_config = [
                    light for light in new_data.get(CONF_LIGHTS, [])
                    if light["entity_id"] not in lights_to_remove
                ]
                new_data[CONF_LIGHTS] = lights_config
                
                return self.async_create_entry(title="", data=new_data)
            
            return await self.async_step_main_menu()

        # Get currently configured lights
        lights_config = self.config_entry.data.get(CONF_LIGHTS, [])
        if not lights_config:
            return self.async_abort(reason="no_lights_configured")

        # Create options for configured lights
        light_options = {}
        for light_config in lights_config:
            entity_id = light_config["entity_id"]
            friendly_name = self._get_entity_name(entity_id)
            light_options[entity_id] = friendly_name

        data_schema = vol.Schema({
            vol.Optional("lights"): cv.multi_select(light_options),
        })

        return self.async_show_form(
            step_id="remove_lights",
            data_schema=data_schema,
        )

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure global settings."""
        if user_input is not None:
            # Update global settings
            new_data = dict(self.config_entry.data)
            new_data.update({
                CONF_MIN_BRIGHTNESS: user_input[CONF_MIN_BRIGHTNESS],
                CONF_MAX_BRIGHTNESS: user_input[CONF_MAX_BRIGHTNESS],
                CONF_MIN_COLOR_TEMP: user_input[CONF_MIN_COLOR_TEMP],
                CONF_MAX_COLOR_TEMP: user_input[CONF_MAX_COLOR_TEMP],
            })
            
            return self.async_create_entry(title="", data=new_data)

        # Get current global settings
        current_data = self.config_entry.data

        data_schema = vol.Schema({
            vol.Required(
                CONF_MIN_BRIGHTNESS, 
                default=current_data.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS)
            ): vol.Range(min=1, max=255),
            vol.Required(
                CONF_MAX_BRIGHTNESS, 
                default=current_data.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS)
            ): vol.Range(min=1, max=255),
            vol.Required(
                CONF_MIN_COLOR_TEMP, 
                default=current_data.get(CONF_MIN_COLOR_TEMP, DEFAULT_MIN_COLOR_TEMP)
            ): vol.Range(min=1000, max=10000),
            vol.Required(
                CONF_MAX_COLOR_TEMP, 
                default=current_data.get(CONF_MAX_COLOR_TEMP, DEFAULT_MAX_COLOR_TEMP)
            ): vol.Range(min=1000, max=10000),
        })

        return self.async_show_form(
            step_id="global_settings",
            data_schema=data_schema,
        )

    def _get_add_lights_schema(self) -> vol.Schema:
        """Get schema for adding lights."""
        # Get available lights that aren't already configured
        configured_lights = {
            light["entity_id"] for light in self.config_entry.data.get(CONF_LIGHTS, [])
        }
        
        available_lights = {}
        for entity in self.hass.states.async_all():
            entity_id = entity.entity_id
            if (entity_id.startswith("light.") and 
                entity.state != "unavailable" and 
                entity_id not in configured_lights):
                
                attributes = entity.attributes
                supported_color_modes = attributes.get("supported_color_modes", [])
                if supported_color_modes:
                    friendly_name = attributes.get("friendly_name", entity_id)
                    available_lights[entity_id] = friendly_name

        return vol.Schema({
            vol.Required("lights"): cv.multi_select(available_lights),
        })

    def _get_entity_name(self, entity_id: str) -> str:
        """Get friendly name for an entity."""
        state = self.hass.states.get(entity_id)
        if state and state.attributes.get("friendly_name"):
            return state.attributes["friendly_name"]
        return entity_id.replace("light.", "").replace("_", " ").title()
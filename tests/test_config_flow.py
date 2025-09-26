"""Test the Simplified Adaptive Lighting config flow."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from custom_components.simplified_adaptive_lighting.config_flow import (
    SimplifiedAdaptiveLightingConfigFlow,
)
from custom_components.simplified_adaptive_lighting.const import (
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


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    
    # Mock states with light entities
    mock_states = {
        "light.living_room": Mock(
            entity_id="light.living_room",
            state="off",
            attributes={
                "friendly_name": "Living Room Light",
                "supported_color_modes": ["color_temp", "brightness"],
                "brightness": 255,
            }
        ),
        "light.bedroom": Mock(
            entity_id="light.bedroom",
            state="on",
            attributes={
                "friendly_name": "Bedroom Light",
                "supported_color_modes": ["hs", "brightness"],
                "brightness": 128,
            }
        ),
        "light.kitchen": Mock(
            entity_id="light.kitchen",
            state="unavailable",
            attributes={
                "friendly_name": "Kitchen Light",
                "supported_color_modes": ["color_temp"],
            }
        ),
        "switch.fan": Mock(
            entity_id="switch.fan",
            state="off",
            attributes={"friendly_name": "Ceiling Fan"}
        ),
    }
    
    hass.states.async_all.return_value = mock_states.values()
    hass.states.get.side_effect = lambda entity_id: mock_states.get(entity_id)
    
    return hass


class TestSimplifiedAdaptiveLightingConfigFlow:
    """Test the config flow."""

    async def test_user_step_form_display(self, mock_hass):
        """Test that the user step displays the form correctly."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        result = await flow.async_step_user()
        
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert CONF_NAME in result["data_schema"].schema
        assert CONF_MIN_BRIGHTNESS in result["data_schema"].schema
        assert CONF_MAX_BRIGHTNESS in result["data_schema"].schema
        assert CONF_MIN_COLOR_TEMP in result["data_schema"].schema
        assert CONF_MAX_COLOR_TEMP in result["data_schema"].schema

    async def test_user_step_valid_input(self, mock_hass):
        """Test user step with valid input proceeds to light selection."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        user_input = {
            CONF_NAME: "Test Adaptive Lighting",
            CONF_MIN_BRIGHTNESS: 10,
            CONF_MAX_BRIGHTNESS: 200,
            CONF_MIN_COLOR_TEMP: 2500,
            CONF_MAX_COLOR_TEMP: 6000,
        }
        
        with patch.object(flow, "async_set_unique_id"), \
             patch.object(flow, "_abort_if_unique_id_configured"), \
             patch.object(flow, "async_step_select_lights") as mock_select_lights:
            
            mock_select_lights.return_value = {"type": "form", "step_id": "select_lights"}
            
            result = await flow.async_step_user(user_input)
            
            assert flow._config == user_input
            mock_select_lights.assert_called_once()

    async def test_user_step_duplicate_name(self, mock_hass):
        """Test user step with duplicate name aborts."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        user_input = {CONF_NAME: "Existing Integration"}
        
        with patch.object(flow, "async_set_unique_id"), \
             patch.object(flow, "_abort_if_unique_id_configured", side_effect=data_entry_flow.AbortFlow("already_configured")):
            
            with pytest.raises(data_entry_flow.AbortFlow):
                await flow.async_step_user(user_input)

    async def test_select_lights_step_form_display(self, mock_hass):
        """Test that the select lights step displays available lights."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        result = await flow.async_step_select_lights()
        
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_lights"
        assert "lights" in result["data_schema"].schema

    async def test_select_lights_step_no_lights_available(self, mock_hass):
        """Test select lights step when no lights are available."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        # Mock no available lights
        mock_hass.states.async_all.return_value = []
        
        result = await flow.async_step_select_lights()
        
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "no_lights_available"

    async def test_select_lights_step_valid_selection(self, mock_hass):
        """Test select lights step with valid light selection."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        user_input = {"lights": ["light.living_room", "light.bedroom"]}
        
        with patch.object(flow, "async_step_configure_lights") as mock_configure:
            mock_configure.return_value = {"type": "form", "step_id": "configure_lights"}
            
            result = await flow.async_step_select_lights(user_input)
            
            assert flow._selected_lights == ["light.living_room", "light.bedroom"]
            mock_configure.assert_called_once()

    async def test_select_lights_step_no_selection(self, mock_hass):
        """Test select lights step with no lights selected."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        user_input = {"lights": []}
        
        result = await flow.async_step_select_lights(user_input)
        
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_lights"
        assert result["errors"]["lights"] == "no_lights_selected"

    async def test_configure_lights_step_form_display(self, mock_hass):
        """Test that the configure lights step displays per-light configuration."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        flow._selected_lights = ["light.living_room", "light.bedroom"]
        
        result = await flow.async_step_configure_lights()
        
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "configure_lights"
        
        # Check that per-light configuration fields are present
        schema_keys = [str(key) for key in result["data_schema"].schema.keys()]
        assert any("light.living_room_white_balance" in key for key in schema_keys)
        assert any("light.living_room_brightness_factor" in key for key in schema_keys)
        assert any("light.bedroom_white_balance" in key for key in schema_keys)
        assert any("light.bedroom_brightness_factor" in key for key in schema_keys)

    async def test_configure_lights_step_create_entry(self, mock_hass):
        """Test configure lights step creates entry with complete configuration."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        flow._config = {
            CONF_NAME: "Test Adaptive Lighting",
            CONF_MIN_BRIGHTNESS: 10,
            CONF_MAX_BRIGHTNESS: 200,
        }
        flow._selected_lights = ["light.living_room", "light.bedroom"]
        
        user_input = {
            "light.living_room_white_balance": 100,
            "light.living_room_brightness_factor": 1.2,
            "light.bedroom_white_balance": -50,
            "light.bedroom_brightness_factor": 0.8,
        }
        
        with patch.object(flow, "async_create_entry") as mock_create:
            mock_create.return_value = {"type": "create_entry"}
            
            result = await flow.async_step_configure_lights(user_input)
            
            # Verify the final configuration structure
            expected_config = {
                CONF_NAME: "Test Adaptive Lighting",
                CONF_MIN_BRIGHTNESS: 10,
                CONF_MAX_BRIGHTNESS: 200,
                CONF_LIGHTS: [
                    {
                        "entity_id": "light.living_room",
                        CONF_WHITE_BALANCE_OFFSET: 100,
                        CONF_BRIGHTNESS_FACTOR: 1.2,
                    },
                    {
                        "entity_id": "light.bedroom",
                        CONF_WHITE_BALANCE_OFFSET: -50,
                        CONF_BRIGHTNESS_FACTOR: 0.8,
                    },
                ]
            }
            
            mock_create.assert_called_once_with(
                title="Test Adaptive Lighting",
                data=expected_config,
            )

    async def test_configure_lights_step_default_values(self, mock_hass):
        """Test configure lights step uses default values when not provided."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        flow._config = {CONF_NAME: "Test"}
        flow._selected_lights = ["light.living_room"]
        
        user_input = {}  # No user input, should use defaults
        
        with patch.object(flow, "async_create_entry") as mock_create:
            mock_create.return_value = {"type": "create_entry"}
            
            await flow.async_step_configure_lights(user_input)
            
            # Verify default values are used
            call_args = mock_create.call_args[1]["data"]
            light_config = call_args[CONF_LIGHTS][0]
            
            assert light_config[CONF_WHITE_BALANCE_OFFSET] == DEFAULT_WHITE_BALANCE_OFFSET
            assert light_config[CONF_BRIGHTNESS_FACTOR] == DEFAULT_BRIGHTNESS_FACTOR

    def test_get_light_entities_filters_correctly(self, mock_hass):
        """Test that _get_light_entities filters entities correctly."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        light_entities = flow._get_light_entities()
        
        # Should include available lights with supported features
        assert "light.living_room" in light_entities
        assert "light.bedroom" in light_entities
        
        # Should exclude unavailable lights and non-light entities
        assert "light.kitchen" not in light_entities  # unavailable
        assert "switch.fan" not in light_entities     # not a light
        
        # Should use friendly names
        assert light_entities["light.living_room"] == "Living Room Light"
        assert light_entities["light.bedroom"] == "Bedroom Light"

    def test_get_entity_name_returns_friendly_name(self, mock_hass):
        """Test that _get_entity_name returns friendly name when available."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        name = flow._get_entity_name("light.living_room")
        assert name == "Living Room Light"

    def test_get_entity_name_fallback_to_entity_id(self, mock_hass):
        """Test that _get_entity_name falls back to formatted entity ID."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        # Mock entity without friendly name
        mock_hass.states.get.return_value = None
        
        name = flow._get_entity_name("light.test_light")
        assert name == "Test Light"

    async def test_validation_brightness_range(self, mock_hass):
        """Test validation of brightness range values."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        # Test invalid brightness values
        user_input = {
            CONF_NAME: "Test",
            CONF_MIN_BRIGHTNESS: 0,  # Below minimum
            CONF_MAX_BRIGHTNESS: 300,  # Above maximum
        }
        
        # The voluptuous schema should handle validation
        # This test ensures the schema is properly configured
        result = await flow.async_step_user()
        schema = result["data_schema"]
        
        # Verify range constraints exist
        min_brightness_field = None
        max_brightness_field = None
        
        for key, validator in schema.schema.items():
            if str(key) == CONF_MIN_BRIGHTNESS:
                min_brightness_field = validator
            elif str(key) == CONF_MAX_BRIGHTNESS:
                max_brightness_field = validator
        
        # Test that range validation exists (voluptuous Range validator)
        assert hasattr(min_brightness_field, 'min')
        assert hasattr(max_brightness_field, 'max')

    async def test_validation_color_temp_range(self, mock_hass):
        """Test validation of color temperature range values."""
        flow = SimplifiedAdaptiveLightingConfigFlow()
        flow.hass = mock_hass
        
        result = await flow.async_step_user()
        schema = result["data_schema"]
        
        # Verify color temperature fields have proper range validation
        min_color_temp_field = None
        max_color_temp_field = None
        
        for key, validator in schema.schema.items():
            if str(key) == CONF_MIN_COLOR_TEMP:
                min_color_temp_field = validator
            elif str(key) == CONF_MAX_COLOR_TEMP:
                max_color_temp_field = validator
        
        assert hasattr(min_color_temp_field, 'min')
        assert hasattr(max_color_temp_field, 'max')
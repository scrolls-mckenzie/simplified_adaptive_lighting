"""Tests for light platform setup."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..light import async_setup_entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        "name": "Test Adaptive Lighting",
        "lights": [
            {
                "entity_id": "light.bedroom",
                "name": "Bedroom Light",
                "white_balance_offset": 100,
                "brightness_factor": 0.9
            },
            {
                "entity_id": "light.living_room",
                "name": "Living Room Light",
                "white_balance_offset": -50,
                "brightness_factor": 1.1
            }
        ]
    }
    return config_entry


@pytest.mark.asyncio
async def test_async_setup_entry(mock_hass, mock_config_entry):
    """Test setting up the light platform."""
    mock_add_entities = AsyncMock()
    
    await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
    
    # Verify entities were added
    mock_add_entities.assert_called_once()
    added_entities = mock_add_entities.call_args[0][0]
    
    # Should have created 2 adaptive light entities
    assert len(added_entities) == 2
    
    # Check first entity
    first_entity = added_entities[0]
    assert first_entity._target_entity_id == "light.bedroom"
    assert first_entity.name == "Adaptive Bedroom Light"
    assert first_entity._white_balance_offset == 100
    assert first_entity._brightness_factor == 0.9
    
    # Check second entity
    second_entity = added_entities[1]
    assert second_entity._target_entity_id == "light.living_room"
    assert second_entity.name == "Adaptive Living Room Light"
    assert second_entity._white_balance_offset == -50
    assert second_entity._brightness_factor == 1.1


@pytest.mark.asyncio
async def test_async_setup_entry_no_lights(mock_hass):
    """Test setting up with no lights configured."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        "name": "Test Adaptive Lighting",
        "lights": []
    }
    
    mock_add_entities = AsyncMock()
    
    await async_setup_entry(mock_hass, config_entry, mock_add_entities)
    
    # Should still call add_entities but with empty list
    mock_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_async_setup_entry_missing_lights_key(mock_hass):
    """Test setting up with missing lights key in config."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        "name": "Test Adaptive Lighting"
        # No "lights" key
    }
    
    mock_add_entities = AsyncMock()
    
    await async_setup_entry(mock_hass, config_entry, mock_add_entities)
    
    # Should handle missing key gracefully
    mock_add_entities.assert_called_once_with([])
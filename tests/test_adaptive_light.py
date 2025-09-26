"""Tests for adaptive light entity."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_TRANSITION
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.restore_state import RestoreStateData

from ..adaptive_light import AdaptiveLight
from ..calculator import TimeBasedCalculator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_calculator():
    """Create a mock calculator."""
    calculator = MagicMock(spec=TimeBasedCalculator)
    calculator.get_brightness_pct.return_value = 80.0  # 80%
    calculator.get_color_temp_kelvin.return_value = 4000  # 4000K
    return calculator


@pytest.fixture
def adaptive_light(mock_hass):
    """Create an adaptive light instance."""
    return AdaptiveLight(
        hass=mock_hass,
        target_entity_id="light.bedroom",
        name="Bedroom Adaptive",
        white_balance_offset=200,
        brightness_factor=0.8
    )


def test_adaptive_light_initialization(adaptive_light):
    """Test adaptive light initialization."""
    assert adaptive_light.name == "Bedroom Adaptive"
    assert adaptive_light._target_entity_id == "light.bedroom"
    assert adaptive_light._white_balance_offset == 200
    assert adaptive_light._brightness_factor == 0.8
    assert adaptive_light.unique_id == "adaptive_light_bedroom"
    assert not adaptive_light.is_on


def test_properties(adaptive_light):
    """Test adaptive light properties."""
    # When off
    assert adaptive_light.brightness is None
    assert adaptive_light.color_temp is None
    
    # When on
    adaptive_light._is_on = True
    adaptive_light._brightness = 128
    adaptive_light._color_temp = 3500
    
    assert adaptive_light.brightness == 128
    assert adaptive_light.color_temp == 3500
    assert adaptive_light.is_on


def test_device_info(adaptive_light):
    """Test device info generation."""
    device_info = adaptive_light.device_info
    
    assert device_info["name"] == "Adaptive Bedroom Adaptive"
    assert device_info["manufacturer"] == "Simplified Adaptive Lighting"
    assert device_info["model"] == "Adaptive Light Controller"


@pytest.mark.asyncio
async def test_async_added_to_hass_no_previous_state(adaptive_light):
    """Test entity added to hass with no previous state."""
    adaptive_light.async_get_last_state = AsyncMock(return_value=None)
    
    await adaptive_light.async_added_to_hass()
    
    # Should remain in default state
    assert not adaptive_light.is_on


@pytest.mark.asyncio
async def test_async_added_to_hass_restore_state(adaptive_light):
    """Test entity added to hass with previous state restoration."""
    # Mock previous state
    last_state = State(
        entity_id="light.adaptive_bedroom",
        state="on",
        attributes={
            ATTR_BRIGHTNESS: 200,
            ATTR_COLOR_TEMP: 3200
        }
    )
    adaptive_light.async_get_last_state = AsyncMock(return_value=last_state)
    
    await adaptive_light.async_added_to_hass()
    
    # Should restore previous state
    assert adaptive_light.is_on
    assert adaptive_light._brightness == 200
    assert adaptive_light._color_temp == 3200


@pytest.mark.asyncio
async def test_async_turn_on_with_adaptive_settings(adaptive_light, mock_calculator):
    """Test turning on with adaptive settings calculation."""
    # Mock the calculator
    with patch.object(adaptive_light, '_calculator', mock_calculator):
        adaptive_light.async_write_ha_state = MagicMock()
        
        await adaptive_light.async_turn_on()
        
        # Verify calculations were called
        mock_calculator.get_brightness_pct.assert_called_once()
        mock_calculator.get_color_temp_kelvin.assert_called_once()
        
        # Verify state updates
        assert adaptive_light.is_on
        
        # Expected calculations:
        # brightness: 80% * 0.8 factor * 255 / 100 = 163.2 -> 163
        # color_temp: 4000 + 200 offset = 4200
        assert adaptive_light._brightness == 163
        assert adaptive_light._color_temp == 4200
        
        # Verify target light was controlled
        adaptive_light.hass.services.async_call.assert_called_once_with(
            "light",
            "turn_on",
            {
                "entity_id": "light.bedroom",
                ATTR_BRIGHTNESS: 163,
                ATTR_COLOR_TEMP: 4200,
                ATTR_TRANSITION: 1
            },
            blocking=True
        )


@pytest.mark.asyncio
async def test_async_turn_on_with_override_values(adaptive_light, mock_calculator):
    """Test turning on with explicit brightness and color temp override."""
    with patch.object(adaptive_light, '_calculator', mock_calculator):
        adaptive_light.async_write_ha_state = MagicMock()
        
        await adaptive_light.async_turn_on(
            brightness=100,
            color_temp=5000,
            transition=3
        )
        
        # Should use override values instead of calculated ones
        assert adaptive_light._brightness == 100
        assert adaptive_light._color_temp == 5000
        
        adaptive_light.hass.services.async_call.assert_called_once_with(
            "light",
            "turn_on",
            {
                "entity_id": "light.bedroom",
                ATTR_BRIGHTNESS: 100,
                ATTR_COLOR_TEMP: 5000,
                ATTR_TRANSITION: 3
            },
            blocking=True
        )


@pytest.mark.asyncio
async def test_async_turn_on_brightness_clamping(adaptive_light, mock_calculator):
    """Test brightness clamping to valid range."""
    # Mock calculator to return extreme values
    mock_calculator.get_brightness_pct.return_value = 5.0  # Very low
    
    with patch.object(adaptive_light, '_calculator', mock_calculator):
        adaptive_light.async_write_ha_state = MagicMock()
        
        await adaptive_light.async_turn_on()
        
        # Brightness should be clamped to minimum of 1
        # 5% * 0.8 * 255 / 100 = 10.2 -> 10, but minimum is 1
        assert adaptive_light._brightness == 10


@pytest.mark.asyncio
async def test_async_turn_on_color_temp_clamping(adaptive_light, mock_calculator):
    """Test color temperature clamping to valid range."""
    # Mock calculator to return extreme values
    mock_calculator.get_color_temp_kelvin.return_value = 1500  # Too low
    
    with patch.object(adaptive_light, '_calculator', mock_calculator):
        adaptive_light.async_write_ha_state = MagicMock()
        
        await adaptive_light.async_turn_on()
        
        # Color temp should be clamped to minimum of 2000K
        # 1500 + 200 offset = 1700, clamped to 2000
        assert adaptive_light._color_temp == 2000


@pytest.mark.asyncio
async def test_async_turn_off(adaptive_light):
    """Test turning off the adaptive light."""
    adaptive_light._is_on = True
    adaptive_light.async_write_ha_state = MagicMock()
    
    await adaptive_light.async_turn_off(transition=2)
    
    assert not adaptive_light.is_on
    
    adaptive_light.hass.services.async_call.assert_called_once_with(
        "light",
        "turn_off",
        {
            "entity_id": "light.bedroom",
            ATTR_TRANSITION: 2
        },
        blocking=True
    )


@pytest.mark.asyncio
async def test_control_target_light_error_handling(adaptive_light):
    """Test error handling when controlling target light fails."""
    adaptive_light.hass.services.async_call.side_effect = Exception("Service call failed")
    
    with pytest.raises(Exception, match="Service call failed"):
        await adaptive_light._control_target_light(turn_on=True, brightness=128)


def test_async_update_settings(adaptive_light):
    """Test updating adaptive light settings."""
    adaptive_light.async_update_settings(
        white_balance_offset=300,
        brightness_factor=1.2
    )
    
    assert adaptive_light._white_balance_offset == 300
    assert adaptive_light._brightness_factor == 1.2


def test_async_update_settings_partial(adaptive_light):
    """Test partially updating adaptive light settings."""
    original_offset = adaptive_light._white_balance_offset
    
    adaptive_light.async_update_settings(brightness_factor=1.5)
    
    # Only brightness factor should change
    assert adaptive_light._white_balance_offset == original_offset
    assert adaptive_light._brightness_factor == 1.5


def test_extra_state_attributes(adaptive_light):
    """Test extra state attributes."""
    attributes = adaptive_light.extra_state_attributes
    
    expected = {
        "target_entity_id": "light.bedroom",
        "white_balance_offset": 200,
        "brightness_factor": 0.8,
        "adaptive_mode": "time_based",
    }
    
    assert attributes == expected
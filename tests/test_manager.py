"""Tests for the AdaptiveLightingManager class."""
from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock Home Assistant modules
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.util'] = MagicMock()
sys.modules['homeassistant.util.dt'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.service'] = MagicMock()
sys.modules['astral'] = MagicMock()
sys.modules['astral.sun'] = MagicMock()

# Mock the classes we need
class MockServiceCall:
    def __init__(self, domain, service, data, context=None):
        self.domain = domain
        self.service = service
        self.data = data
        self.context = context or MagicMock()

class MockContext:
    pass

# Now import our modules
from simplified_adaptive_lighting.manager import AdaptiveLightingManager
from simplified_adaptive_lighting.models import LightConfig, AdaptiveSettings
from simplified_adaptive_lighting.const import (
    CONF_LIGHTS,
    CONF_MIN_BRIGHTNESS,
    CONF_MAX_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP,
    CONF_MAX_COLOR_TEMP,
)


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.latitude = 40.7128
    hass.config.longitude = -74.0060
    hass.config.time_zone = "America/New_York"
    
    # Mock services
    services = MagicMock()
    services._services = {
        "light": {
            "turn_on": MagicMock(),
            "toggle": MagicMock(),
        }
    }
    services.has_service.return_value = True
    hass.services = services
    
    return hass


@pytest.fixture
def sample_config():
    """Create a sample configuration."""
    return {
        CONF_LIGHTS: [
            {
                "entity_id": "light.living_room",
                "white_balance_offset": 100,
                "brightness_factor": 0.8,
                "enabled": True,
            },
            {
                "entity_id": "light.bedroom",
                "white_balance_offset": -50,
                "brightness_factor": 1.2,
                "enabled": True,
            },
        ],
        CONF_MIN_BRIGHTNESS: 10,
        CONF_MAX_BRIGHTNESS: 255,
        CONF_MIN_COLOR_TEMP: 2000,
        CONF_MAX_COLOR_TEMP: 6500,
    }


@pytest.fixture
def manager(hass, sample_config):
    """Create an AdaptiveLightingManager instance."""
    return AdaptiveLightingManager(hass, sample_config)


class TestAdaptiveLightingManager:
    """Test the AdaptiveLightingManager class."""
    
    def test_initialization(self, manager, sample_config):
        """Test manager initialization."""
        assert len(manager._lights) == 2
        assert "light.living_room" in manager._lights
        assert "light.bedroom" in manager._lights
        
        # Check light configurations
        living_room = manager._lights["light.living_room"]
        assert living_room.white_balance_offset == 100
        assert living_room.brightness_factor == 0.8
        
        bedroom = manager._lights["light.bedroom"]
        assert bedroom.white_balance_offset == -50
        assert bedroom.brightness_factor == 1.2
        
        # Check calculator configuration
        assert manager._calculator.min_brightness == 10
        assert manager._calculator.max_brightness == 255
        assert manager._calculator.min_color_temp == 2000
        assert manager._calculator.max_color_temp == 6500
    
    async def test_setup(self, manager):
        """Test manager setup."""
        result = await manager.setup()
        assert result is True
    
    async def test_enable_interception(self, manager):
        """Test enabling service call interception."""
        await manager.enable_interception()
        
        assert manager.is_interception_enabled
        assert len(manager._original_handlers) == 2
        
        # Verify services were replaced
        manager.hass.services.async_remove.assert_called()
        manager.hass.services.async_register.assert_called()
    
    async def test_disable_interception(self, manager):
        """Test disabling service call interception."""
        # First enable interception
        await manager.enable_interception()
        assert manager.is_interception_enabled
        
        # Then disable it
        await manager.disable_interception()
        
        assert not manager.is_interception_enabled
        assert len(manager._original_handlers) == 0
    
    def test_calculate_adaptive_settings(self, manager):
        """Test calculating adaptive settings for a light."""
        with patch('simplified_adaptive_lighting.manager.datetime') as mock_datetime:
            # Mock a specific time (noon)
            mock_datetime.now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            
            settings = manager.calculate_adaptive_settings("light.living_room")
            
            assert isinstance(settings, AdaptiveSettings)
            assert 1 <= settings.brightness <= 255
            assert 1000 <= settings.color_temp_kelvin <= 10000
            assert settings.transition == 1
    
    def test_apply_white_balance(self, manager):
        """Test white balance correction."""
        # Test with configured light
        corrected_temp = manager.apply_white_balance("light.living_room", 3000)
        assert corrected_temp == 3100  # 3000 + 100 offset
        
        # Test with different light
        corrected_temp = manager.apply_white_balance("light.bedroom", 4000)
        assert corrected_temp == 3950  # 4000 - 50 offset
        
        # Test with unconfigured light
        corrected_temp = manager.apply_white_balance("light.unknown", 3000)
        assert corrected_temp == 3000  # No change
        
        # Test clamping
        corrected_temp = manager.apply_white_balance("light.living_room", 9950)
        assert corrected_temp == 10000  # Clamped to max
    
    async def test_async_intercept_service_call_single_adaptive_light(self, manager):
        """Test intercepting service call for single adaptive light."""
        # Setup interception
        await manager.enable_interception()
        
        # Mock original handler
        original_handler = MagicMock()
        original_handler.job.target = AsyncMock()
        manager._original_handlers["light.turn_on"] = original_handler
        
        # Create service call
        call = MockServiceCall(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.living_room"},
            context=MockContext(),
        )
        
        with patch.object(manager, 'calculate_adaptive_settings') as mock_calc:
            mock_settings = AdaptiveSettings(brightness=128, color_temp_kelvin=3500)
            mock_calc.return_value = mock_settings
            
            await manager.async_intercept_service_call(call)
            
            # Verify adaptive settings were calculated
            mock_calc.assert_called_once_with("light.living_room")
            
            # Verify original handler was called with modified data
            original_handler.job.target.assert_called_once()
            called_call = original_handler.job.target.call_args[0][0]
            assert called_call.data["brightness"] == 128
            assert called_call.data["kelvin"] == 3500
    
    async def test_async_intercept_service_call_non_adaptive_light(self, manager):
        """Test intercepting service call for non-adaptive light."""
        # Setup interception
        await manager.enable_interception()
        
        # Mock original handler
        original_handler = MagicMock()
        original_handler.job.target = AsyncMock()
        manager._original_handlers["light.turn_on"] = original_handler
        
        # Create service call for non-adaptive light
        call = MockServiceCall(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.kitchen"},
            context=MockContext(),
        )
        
        await manager.async_intercept_service_call(call)
        
        # Verify original handler was called with unchanged data
        original_handler.job.target.assert_called_once_with(call)
    
    async def test_async_intercept_service_call_mixed_entities(self, manager):
        """Test intercepting service call with mixed adaptive and non-adaptive lights."""
        # Setup interception
        await manager.enable_interception()
        
        # Mock original handler
        original_handler = MagicMock()
        original_handler.job.target = AsyncMock()
        manager._original_handlers["light.turn_on"] = original_handler
        
        # Create service call with mixed entities
        call = MockServiceCall(
            domain="light",
            service="turn_on",
            data={"entity_id": ["light.living_room", "light.kitchen", "light.bedroom"]},
            context=MockContext(),
        )
        
        with patch.object(manager, 'calculate_adaptive_settings') as mock_calc:
            mock_settings = AdaptiveSettings(brightness=128, color_temp_kelvin=3500)
            mock_calc.return_value = mock_settings
            
            await manager.async_intercept_service_call(call)
            
            # Verify adaptive settings were calculated for adaptive lights
            assert mock_calc.call_count == 2  # living_room and bedroom
            
            # Verify original handler was called multiple times
            assert original_handler.job.target.call_count == 3  # 1 non-adaptive + 2 adaptive
    
    async def test_async_intercept_service_call_error_handling(self, manager):
        """Test error handling in service call interception."""
        # Setup interception
        await manager.enable_interception()
        
        # Mock original handler
        original_handler = MagicMock()
        original_handler.job.target = AsyncMock()
        manager._original_handlers["light.turn_on"] = original_handler
        
        # Create service call
        call = MockServiceCall(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.living_room"},
            context=MockContext(),
        )
        
        # Mock calculate_adaptive_settings to raise an exception
        with patch.object(manager, 'calculate_adaptive_settings', side_effect=Exception("Test error")):
            await manager.async_intercept_service_call(call)
            
            # Verify fallback to original call
            original_handler.job.target.assert_called_with(call)
    
    def test_configured_lights_property(self, manager):
        """Test the configured_lights property."""
        lights = manager.configured_lights
        assert len(lights) == 2
        assert "light.living_room" in lights
        assert "light.bedroom" in lights
    
    def test_brightness_factor_application(self, manager):
        """Test that brightness factor is applied correctly."""
        with patch('simplified_adaptive_lighting.manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            
            # Mock calculator to return a known brightness
            with patch.object(manager._calculator, 'get_brightness_value', return_value=100):
                settings = manager.calculate_adaptive_settings("light.living_room")
                # brightness_factor is 0.8, so 100 * 0.8 = 80
                assert settings.brightness == 80
                
                settings = manager.calculate_adaptive_settings("light.bedroom")
                # brightness_factor is 1.2, so 100 * 1.2 = 120
                assert settings.brightness == 120
    
    def test_brightness_clamping(self, manager):
        """Test that brightness values are clamped to valid range."""
        with patch('simplified_adaptive_lighting.manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            
            # Test lower bound clamping
            with patch.object(manager._calculator, 'get_brightness_value', return_value=1):
                # Even with factor 0.8, should not go below 1
                settings = manager.calculate_adaptive_settings("light.living_room")
                assert settings.brightness >= 1
            
            # Test upper bound clamping
            with patch.object(manager._calculator, 'get_brightness_value', return_value=250):
                # With factor 1.2, 250 * 1.2 = 300, should be clamped to 255
                settings = manager.calculate_adaptive_settings("light.bedroom")
                assert settings.brightness <= 255


class TestWhiteBalanceAndBrightnessCorrections:
    """Test white balance and brightness correction functionality."""
    
    def test_apply_brightness_correction_configured_light(self, manager):
        """Test brightness correction for configured light."""
        # Test living room (factor 0.8)
        corrected = manager.apply_brightness_correction("light.living_room", 100)
        assert corrected == 80  # 100 * 0.8
        
        # Test bedroom (factor 1.2)
        corrected = manager.apply_brightness_correction("light.bedroom", 100)
        assert corrected == 120  # 100 * 1.2
    
    def test_apply_brightness_correction_unconfigured_light(self, manager):
        """Test brightness correction for unconfigured light."""
        corrected = manager.apply_brightness_correction("light.unknown", 100)
        assert corrected == 100  # No change
    
    def test_apply_brightness_correction_clamping(self, manager):
        """Test brightness correction clamping to valid range."""
        # Test lower bound clamping
        corrected = manager.apply_brightness_correction("light.living_room", 1)
        assert corrected >= 1
        
        # Test upper bound clamping with high factor
        corrected = manager.apply_brightness_correction("light.bedroom", 250)
        assert corrected <= 255
    
    def test_apply_white_balance_configured_light(self, manager):
        """Test white balance correction for configured light."""
        # Test living room (+100K offset)
        corrected = manager.apply_white_balance("light.living_room", 3000)
        assert corrected == 3100
        
        # Test bedroom (-50K offset)
        corrected = manager.apply_white_balance("light.bedroom", 4000)
        assert corrected == 3950
    
    def test_apply_white_balance_unconfigured_light(self, manager):
        """Test white balance correction for unconfigured light."""
        corrected = manager.apply_white_balance("light.unknown", 3000)
        assert corrected == 3000  # No change
    
    def test_apply_white_balance_clamping(self, manager):
        """Test white balance correction clamping to valid range."""
        # Test upper bound clamping
        corrected = manager.apply_white_balance("light.living_room", 6450)
        assert corrected == manager._calculator.max_color_temp  # Should clamp to 6500
        
        # Test lower bound clamping
        corrected = manager.apply_white_balance("light.bedroom", 2100)
        assert corrected >= manager._calculator.min_color_temp  # Should clamp to 2000
    
    def test_get_light_corrections_configured(self, manager):
        """Test getting corrections for configured light."""
        corrections = manager.get_light_corrections("light.living_room")
        
        assert corrections["white_balance_offset"] == 100
        assert corrections["brightness_factor"] == 0.8
        assert corrections["enabled"] is True
    
    def test_get_light_corrections_unconfigured(self, manager):
        """Test getting corrections for unconfigured light."""
        corrections = manager.get_light_corrections("light.unknown")
        
        assert corrections["white_balance_offset"] == 0
        assert corrections["brightness_factor"] == 1.0
        assert corrections["enabled"] is False
    
    def test_validate_corrections_consistency_valid(self, manager):
        """Test validation with valid correction settings."""
        result = manager.validate_corrections_consistency()
        assert result is True
    
    def test_validate_corrections_consistency_invalid_white_balance(self, hass):
        """Test validation with invalid white balance offset."""
        invalid_config = {
            CONF_LIGHTS: [
                {
                    "entity_id": "light.invalid",
                    "white_balance_offset": 2000,  # Too high
                    "brightness_factor": 1.0,
                    "enabled": True,
                }
            ]
        }
        
        invalid_manager = AdaptiveLightingManager(hass, invalid_config)
        result = invalid_manager.validate_corrections_consistency()
        assert result is False
    
    def test_validate_corrections_consistency_invalid_brightness_factor(self, hass):
        """Test validation with invalid brightness factor."""
        invalid_config = {
            CONF_LIGHTS: [
                {
                    "entity_id": "light.invalid",
                    "white_balance_offset": 0,
                    "brightness_factor": 5.0,  # Too high
                    "enabled": True,
                }
            ]
        }
        
        invalid_manager = AdaptiveLightingManager(hass, invalid_config)
        result = invalid_manager.validate_corrections_consistency()
        assert result is False
    
    def test_corrections_applied_consistently_single_light(self, manager):
        """Test that corrections are applied consistently for single light calls."""
        with patch('simplified_adaptive_lighting.manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            
            # Mock calculator to return known values
            with patch.object(manager._calculator, 'get_brightness_value', return_value=200), \
                 patch.object(manager._calculator, 'get_color_temp_kelvin', return_value=4000):
                
                settings = manager.calculate_adaptive_settings("light.living_room")
                
                # Verify corrections were applied
                assert settings.brightness == 160  # 200 * 0.8
                assert settings.color_temp_kelvin == 4100  # 4000 + 100
    
    def test_corrections_applied_consistently_multiple_calls(self, manager):
        """Test that corrections are applied consistently across multiple calls."""
        with patch('simplified_adaptive_lighting.manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            
            # Mock calculator to return known values
            with patch.object(manager._calculator, 'get_brightness_value', return_value=150), \
                 patch.object(manager._calculator, 'get_color_temp_kelvin', return_value=3500):
                
                # Call multiple times for same light
                settings1 = manager.calculate_adaptive_settings("light.bedroom")
                settings2 = manager.calculate_adaptive_settings("light.bedroom")
                
                # Should be identical
                assert settings1.brightness == settings2.brightness == 180  # 150 * 1.2
                assert settings1.color_temp_kelvin == settings2.color_temp_kelvin == 3450  # 3500 - 50
    
    def test_realistic_correction_scenarios(self, manager):
        """Test realistic correction scenarios with various light types."""
        test_scenarios = [
            {
                "entity_id": "light.living_room",
                "base_brightness": 100,
                "base_color_temp": 3000,
                "expected_brightness": 80,  # 100 * 0.8
                "expected_color_temp": 3100,  # 3000 + 100
            },
            {
                "entity_id": "light.bedroom", 
                "base_brightness": 200,
                "base_color_temp": 5000,
                "expected_brightness": 240,  # 200 * 1.2
                "expected_color_temp": 4950,  # 5000 - 50
            }
        ]
        
        for scenario in test_scenarios:
            brightness = manager.apply_brightness_correction(
                scenario["entity_id"], 
                scenario["base_brightness"]
            )
            color_temp = manager.apply_white_balance(
                scenario["entity_id"], 
                scenario["base_color_temp"]
            )
            
            assert brightness == scenario["expected_brightness"]
            assert color_temp == scenario["expected_color_temp"]


class TestAdaptiveSettingsIntegration:
    """Test integration between manager and adaptive settings."""
    
    def test_adaptive_settings_to_service_data(self):
        """Test conversion of adaptive settings to service data."""
        settings = AdaptiveSettings(
            brightness=128,
            color_temp_kelvin=3500,
            transition=2,
        )
        
        service_data = settings.to_service_data()
        
        assert service_data["brightness"] == 128
        assert service_data["kelvin"] == 3500
        assert service_data["transition"] == 2
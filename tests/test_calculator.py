"""Tests for the TimeBasedCalculator class."""
from __future__ import annotations

import math
import sys
from datetime import datetime, time, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

# Mock Home Assistant modules
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.util'] = MagicMock()
sys.modules['homeassistant.util.dt'] = MagicMock()
sys.modules['astral'] = MagicMock()
sys.modules['astral.sun'] = MagicMock()

# Now import our module
from simplified_adaptive_lighting.calculator import TimeBasedCalculator


class TestTimeBasedCalculator:
    """Test the TimeBasedCalculator class."""
    
    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.config.latitude = 40.7128  # New York
        hass.config.longitude = -74.0060
        hass.config.time_zone = "America/New_York"
        return hass
    
    @pytest.fixture
    def calculator(self, mock_hass):
        """Create a TimeBasedCalculator instance."""
        return TimeBasedCalculator(
            hass=mock_hass,
            min_brightness=1,
            max_brightness=255,
            min_color_temp=2000,
            max_color_temp=6500,
        )
    
    def test_init(self, mock_hass):
        """Test calculator initialization."""
        calc = TimeBasedCalculator(
            hass=mock_hass,
            min_brightness=10,
            max_brightness=200,
            min_color_temp=2500,
            max_color_temp=6000,
        )
        
        assert calc.hass is mock_hass
        assert calc.min_brightness == 10
        assert calc.max_brightness == 200
        assert calc.min_color_temp == 2500
        assert calc.max_color_temp == 6000
    
    def test_get_location_info(self, calculator):
        """Test location info retrieval."""
        location = calculator._get_location_info()
        
        assert location.name == "Home Assistant"
        assert location.latitude == 40.7128
        assert location.longitude == -74.0060
        assert str(location.timezone) == "America/New_York"
    
    @patch('simplified_adaptive_lighting.calculator.sun')
    def test_get_sun_times_success(self, mock_sun, calculator):
        """Test successful sun times calculation."""
        # Mock sun times
        test_date = datetime(2024, 6, 21, 12, 0, 0)  # Summer solstice
        mock_sun_times = {
            'sunrise': datetime(2024, 6, 21, 5, 30, 0),
            'sunset': datetime(2024, 6, 21, 20, 0, 0),
            'noon': datetime(2024, 6, 21, 12, 45, 0),
        }
        mock_sun.return_value = mock_sun_times
        
        sun_times = calculator._get_sun_times(test_date)
        
        assert 'sunrise' in sun_times
        assert 'sunset' in sun_times
        assert 'noon' in sun_times
        mock_sun.assert_called_once()
    
    @patch('simplified_adaptive_lighting.calculator.sun')
    def test_get_sun_times_fallback(self, mock_sun, calculator):
        """Test fallback sun times when astral fails."""
        mock_sun.side_effect = Exception("Astral error")
        
        test_date = datetime(2024, 6, 21, 12, 0, 0)
        sun_times = calculator._get_sun_times(test_date)
        
        # Should return fallback times
        assert sun_times['sunrise'].time() == time(6, 0)
        assert sun_times['sunset'].time() == time(18, 0)
        assert sun_times['noon'].time() == time(12, 0)
    
    def test_sun_position_factor_night(self, calculator):
        """Test sun position factor during night."""
        # Mock sun times for testing
        with patch.object(calculator, '_get_sun_times') as mock_sun_times:
            mock_sun_times.return_value = {
                'sunrise': datetime(2024, 6, 21, 6, 0, 0),
                'sunset': datetime(2024, 6, 21, 18, 0, 0),
                'noon': datetime(2024, 6, 21, 12, 0, 0),
            }
            
            # Test deep night (before sunrise transition)
            night_time = datetime(2024, 6, 21, 2, 0, 0)
            factor = calculator._get_sun_position_factor(night_time)
            assert factor == 0.0
            
            # Test late night (after sunset transition)
            late_night = datetime(2024, 6, 21, 22, 0, 0)
            factor = calculator._get_sun_position_factor(late_night)
            assert factor == 0.0
    
    def test_sun_position_factor_day(self, calculator):
        """Test sun position factor during day."""
        with patch.object(calculator, '_get_sun_times') as mock_sun_times:
            mock_sun_times.return_value = {
                'sunrise': datetime(2024, 6, 21, 6, 0, 0),
                'sunset': datetime(2024, 6, 21, 18, 0, 0),
                'noon': datetime(2024, 6, 21, 12, 0, 0),
            }
            
            # Test mid-day (should be high)
            midday = datetime(2024, 6, 21, 12, 0, 0)
            factor = calculator._get_sun_position_factor(midday)
            assert factor > 0.8  # Should be near peak
            
            # Test morning (should be moderate)
            morning = datetime(2024, 6, 21, 9, 0, 0)
            factor = calculator._get_sun_position_factor(morning)
            assert 0.3 < factor < 0.9
    
    def test_sun_position_factor_transitions(self, calculator):
        """Test sun position factor during sunrise/sunset transitions."""
        with patch.object(calculator, '_get_sun_times') as mock_sun_times:
            mock_sun_times.return_value = {
                'sunrise': datetime(2024, 6, 21, 6, 0, 0),
                'sunset': datetime(2024, 6, 21, 18, 0, 0),
                'noon': datetime(2024, 6, 21, 12, 0, 0),
            }
            
            # Test sunrise transition
            sunrise_time = datetime(2024, 6, 21, 6, 0, 0)
            factor = calculator._get_sun_position_factor(sunrise_time)
            assert 0.0 < factor < 1.0
            
            # Test sunset transition
            sunset_time = datetime(2024, 6, 21, 18, 0, 0)
            factor = calculator._get_sun_position_factor(sunset_time)
            assert 0.0 < factor < 1.0
    
    def test_get_brightness_pct(self, calculator):
        """Test brightness percentage calculation."""
        # Test with mocked sun position
        with patch.object(calculator, '_get_sun_position_factor') as mock_factor:
            # Test night (factor = 0.0)
            mock_factor.return_value = 0.0
            brightness = calculator.get_brightness_pct()
            expected_min = calculator.min_brightness / 255.0
            assert brightness == expected_min
            
            # Test peak day (factor = 1.0)
            mock_factor.return_value = 1.0
            brightness = calculator.get_brightness_pct()
            expected_max = calculator.max_brightness / 255.0
            assert brightness == expected_max
            
            # Test mid-day (factor = 0.5)
            mock_factor.return_value = 0.5
            brightness = calculator.get_brightness_pct()
            expected_mid = expected_min + (expected_max - expected_min) * 0.5
            assert abs(brightness - expected_mid) < 0.01
    
    def test_get_brightness_value(self, calculator):
        """Test brightness value calculation."""
        with patch.object(calculator, 'get_brightness_pct') as mock_pct:
            mock_pct.return_value = 0.5
            brightness = calculator.get_brightness_value()
            assert brightness == int(0.5 * 255)
    
    def test_get_color_temp_kelvin(self, calculator):
        """Test color temperature calculation."""
        with patch.object(calculator, '_get_sun_position_factor') as mock_factor:
            # Test night (factor = 0.0) - should be warm
            mock_factor.return_value = 0.0
            temp = calculator.get_color_temp_kelvin()
            assert temp == calculator.min_color_temp
            
            # Test peak day (factor = 1.0) - should be cool
            mock_factor.return_value = 1.0
            temp = calculator.get_color_temp_kelvin()
            assert temp == calculator.max_color_temp
            
            # Test mid-day (factor = 0.5)
            mock_factor.return_value = 0.5
            temp = calculator.get_color_temp_kelvin()
            expected = calculator.min_color_temp + (calculator.max_color_temp - calculator.min_color_temp) * 0.5
            assert abs(temp - expected) < 10
    
    def test_apply_white_balance_correction(self, calculator):
        """Test white balance correction."""
        base_temp = 4000
        
        # Test positive offset
        corrected = calculator.apply_white_balance_correction(base_temp, 500)
        assert corrected == 4500
        
        # Test negative offset
        corrected = calculator.apply_white_balance_correction(base_temp, -300)
        assert corrected == 3700
        
        # Test no offset
        corrected = calculator.apply_white_balance_correction(base_temp, 0)
        assert corrected == base_temp
        
        # Test clamping to min
        corrected = calculator.apply_white_balance_correction(2100, -500)
        assert corrected == calculator.min_color_temp
        
        # Test clamping to max
        corrected = calculator.apply_white_balance_correction(6400, 500)
        assert corrected == calculator.max_color_temp
    
    def test_apply_brightness_factor(self, calculator):
        """Test brightness factor correction."""
        base_brightness = 128
        
        # Test factor > 1.0
        corrected = calculator.apply_brightness_factor(base_brightness, 1.5)
        assert corrected == int(128 * 1.5)
        
        # Test factor < 1.0
        corrected = calculator.apply_brightness_factor(base_brightness, 0.5)
        assert corrected == int(128 * 0.5)
        
        # Test factor = 1.0
        corrected = calculator.apply_brightness_factor(base_brightness, 1.0)
        assert corrected == base_brightness
        
        # Test clamping to min
        corrected = calculator.apply_brightness_factor(5, 0.1)
        assert corrected == 1
        
        # Test clamping to max
        corrected = calculator.apply_brightness_factor(200, 2.0)
        assert corrected == 255
    
    def test_get_adaptive_settings(self, calculator):
        """Test complete adaptive settings calculation."""
        test_time = datetime(2024, 6, 21, 12, 0, 0)
        
        with patch.object(calculator, 'get_brightness_value') as mock_brightness, \
             patch.object(calculator, 'get_color_temp_kelvin') as mock_temp:
            
            mock_brightness.return_value = 200
            mock_temp.return_value = 5000
            
            # Test with corrections
            settings = calculator.get_adaptive_settings(
                dt=test_time,
                white_balance_offset=200,
                brightness_factor=0.8,
            )
            
            assert settings["brightness"] == int(200 * 0.8)
            assert settings["color_temp_kelvin"] == 5200
            
            # Test without corrections
            settings = calculator.get_adaptive_settings(dt=test_time)
            assert settings["brightness"] == 200
            assert settings["color_temp_kelvin"] == 5000
    
    def test_edge_cases(self, calculator):
        """Test edge cases and boundary conditions."""
        # Test with extreme white balance offsets
        extreme_positive = calculator.apply_white_balance_correction(3000, 5000)
        assert extreme_positive == calculator.max_color_temp
        
        extreme_negative = calculator.apply_white_balance_correction(3000, -5000)
        assert extreme_negative == calculator.min_color_temp
        
        # Test with extreme brightness factors
        extreme_high = calculator.apply_brightness_factor(100, 10.0)
        assert extreme_high == 255
        
        extreme_low = calculator.apply_brightness_factor(100, 0.001)
        assert extreme_low == 1
    
    def test_realistic_scenarios(self, calculator):
        """Test realistic usage scenarios."""
        # Test typical morning scenario
        morning = datetime(2024, 6, 21, 7, 30, 0)
        settings = calculator.get_adaptive_settings(
            dt=morning,
            white_balance_offset=-100,  # Slightly warmer
            brightness_factor=0.9,      # Slightly dimmer
        )
        
        assert 1 <= settings["brightness"] <= 255
        assert calculator.min_color_temp <= settings["color_temp_kelvin"] <= calculator.max_color_temp
        
        # Test typical evening scenario
        evening = datetime(2024, 6, 21, 19, 30, 0)
        settings = calculator.get_adaptive_settings(
            dt=evening,
            white_balance_offset=100,   # Slightly cooler
            brightness_factor=1.2,      # Slightly brighter
        )
        
        assert 1 <= settings["brightness"] <= 255
        assert calculator.min_color_temp <= settings["color_temp_kelvin"] <= calculator.max_color_temp
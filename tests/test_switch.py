"""Tests for the Simplified Adaptive Lighting switch platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.simplified_adaptive_lighting.const import DOMAIN
from custom_components.simplified_adaptive_lighting.manager import AdaptiveLightingManager
from custom_components.simplified_adaptive_lighting.switch import (
    AdaptiveLightingSwitch,
    async_setup_entry,
)


@pytest.fixture
def mock_manager():
    """Create a mock adaptive lighting manager."""
    manager = MagicMock(spec=AdaptiveLightingManager)
    manager.enable_interception = AsyncMock()
    manager.disable_interception = AsyncMock()
    manager.is_interception_enabled = False
    return manager


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry_id"
    config_entry.data = {
        CONF_NAME: "Test Adaptive Lighting",
        "lights": [
            {"entity_id": "light.test_light_1"},
            {"entity_id": "light.test_light_2"},
        ],
    }
    return config_entry


@pytest.fixture
def switch(hass: HomeAssistant, mock_config_entry, mock_manager):
    """Create an adaptive lighting switch."""
    return AdaptiveLightingSwitch(
        hass=hass,
        config_entry=mock_config_entry,
        manager=mock_manager,
        name="Test Adaptive Lighting",
        unique_id="test_entry_id",
    )


class TestAsyncSetupEntry:
    """Test the async_setup_entry function."""

    async def test_async_setup_entry_success(self, hass: HomeAssistant, mock_config_entry, mock_manager):
        """Test setting up the switch platform successfully."""
        # Setup domain data with new structure
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "manager": mock_manager,
                "config": mock_config_entry.data,
            }
        }
        
        # Mock add_entities callback
        add_entities_callback = MagicMock(spec=AddEntitiesCallback)
        
        # Call setup
        await async_setup_entry(hass, mock_config_entry, add_entities_callback)
        
        # Verify switch was created and added
        add_entities_callback.assert_called_once()
        switches = add_entities_callback.call_args[0][0]
        assert len(switches) == 1
        assert isinstance(switches[0], AdaptiveLightingSwitch)
        
        # Verify switch properties
        switch = switches[0]
        assert switch.name == "Test Adaptive Lighting"
        assert switch.unique_id == "test_entry_id"
        assert switch._manager is mock_manager

    async def test_async_setup_entry_missing_manager(self, hass: HomeAssistant, mock_config_entry):
        """Test setup failure when manager is missing."""
        # Setup domain data without manager
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "config": mock_config_entry.data,
            }
        }
        
        add_entities_callback = MagicMock(spec=AddEntitiesCallback)
        
        with pytest.raises(KeyError):
            await async_setup_entry(hass, mock_config_entry, add_entities_callback)
        
        add_entities_callback.assert_not_called()

    async def test_async_setup_entry_missing_entry_data(self, hass: HomeAssistant, mock_config_entry):
        """Test setup failure when entry data is missing."""
        # Setup domain data without entry
        hass.data[DOMAIN] = {}
        
        add_entities_callback = MagicMock(spec=AddEntitiesCallback)
        
        with pytest.raises(KeyError):
            await async_setup_entry(hass, mock_config_entry, add_entities_callback)
        
        add_entities_callback.assert_not_called()

    async def test_async_setup_entry_no_domain_data(self, hass: HomeAssistant, mock_config_entry):
        """Test setup failure when domain data is missing."""
        add_entities_callback = MagicMock(spec=AddEntitiesCallback)
        
        with pytest.raises(KeyError):
            await async_setup_entry(hass, mock_config_entry, add_entities_callback)
        
        add_entities_callback.assert_not_called()


class TestAdaptiveLightingSwitch:
    """Test the AdaptiveLightingSwitch class."""

    def test_init(self, hass: HomeAssistant, mock_config_entry, mock_manager):
        """Test switch initialization."""
        switch = AdaptiveLightingSwitch(
            hass=hass,
            config_entry=mock_config_entry,
            manager=mock_manager,
            name="Test Switch",
            unique_id="test_unique_id",
        )
        
        assert switch.hass is hass
        assert switch._config_entry is mock_config_entry
        assert switch._manager is mock_manager
        assert switch.name == "Test Switch"
        assert switch.unique_id == "test_unique_id"
        assert switch.icon == "mdi:lightbulb-auto"
        assert switch.is_on is False

    def test_device_info(self, hass: HomeAssistant, mock_config_entry, mock_manager):
        """Test device info for device registry integration."""
        switch = AdaptiveLightingSwitch(
            hass=hass,
            config_entry=mock_config_entry,
            manager=mock_manager,
            name="Test Switch",
            unique_id="test_unique_id",
        )
        
        device_info = switch.device_info
        
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, mock_config_entry.entry_id)}
        assert device_info["name"] == "Simplified Adaptive Lighting (Test Switch)"
        assert device_info["manufacturer"] == "Simplified Adaptive Lighting"
        assert device_info["model"] == "Adaptive Lighting Controller"
        assert device_info["sw_version"] == "1.0.0"
        assert device_info["configuration_url"] is None

    def test_is_on_property(self, switch):
        """Test the is_on property."""
        assert switch.is_on is False
        
        switch._is_on = True
        assert switch.is_on is True

    def test_extra_state_attributes(self, switch):
        """Test extra state attributes."""
        switch._manager.is_interception_enabled = True
        
        attributes = switch.extra_state_attributes
        
        assert attributes["adaptive_lights_count"] == 2
        assert attributes["configured_lights"] == ["light.test_light_1", "light.test_light_2"]
        assert attributes["interception_enabled"] is True

    async def test_async_turn_on_success(self, switch):
        """Test successfully turning on adaptive lighting."""
        switch._manager.enable_interception = AsyncMock()
        
        await switch.async_turn_on()
        
        switch._manager.enable_interception.assert_called_once()
        assert switch.is_on is True

    async def test_async_turn_on_failure(self, switch):
        """Test handling failure when turning on adaptive lighting."""
        switch._manager.enable_interception = AsyncMock(side_effect=Exception("Test error"))
        switch._manager.is_interception_enabled = False
        
        await switch.async_turn_on()
        
        switch._manager.enable_interception.assert_called_once()
        assert switch.is_on is False  # Should reflect actual manager state

    async def test_async_turn_off_success(self, switch):
        """Test successfully turning off adaptive lighting."""
        switch._is_on = True
        switch._manager.disable_interception = AsyncMock()
        
        await switch.async_turn_off()
        
        switch._manager.disable_interception.assert_called_once()
        assert switch.is_on is False

    async def test_async_turn_off_failure(self, switch):
        """Test handling failure when turning off adaptive lighting."""
        switch._is_on = True
        switch._manager.disable_interception = AsyncMock(side_effect=Exception("Test error"))
        switch._manager.is_interception_enabled = True
        
        await switch.async_turn_off()
        
        switch._manager.disable_interception.assert_called_once()
        assert switch.is_on is True  # Should reflect actual manager state

    async def test_async_turn_on_interception_verification_success(self, switch):
        """Test turn on with successful interception verification."""
        switch._manager.enable_interception = AsyncMock()
        switch._manager.is_interception_enabled = True
        
        await switch.async_turn_on()
        
        switch._manager.enable_interception.assert_called_once()
        assert switch.is_on is True

    async def test_async_turn_on_interception_verification_failure(self, switch):
        """Test turn on with failed interception verification."""
        switch._manager.enable_interception = AsyncMock()
        switch._manager.is_interception_enabled = False  # Interception didn't actually start
        
        await switch.async_turn_on()
        
        switch._manager.enable_interception.assert_called_once()
        assert switch.is_on is False

    async def test_async_turn_on_with_cleanup_on_failure(self, switch):
        """Test turn on with cleanup when enable fails."""
        switch._manager.enable_interception = AsyncMock(side_effect=Exception("Test error"))
        switch._manager.disable_interception = AsyncMock()
        
        await switch.async_turn_on()
        
        switch._manager.enable_interception.assert_called_once()
        switch._manager.disable_interception.assert_called_once()
        assert switch.is_on is False

    async def test_async_turn_on_cleanup_failure(self, switch):
        """Test turn on with cleanup failure."""
        switch._manager.enable_interception = AsyncMock(side_effect=Exception("Enable error"))
        switch._manager.disable_interception = AsyncMock(side_effect=Exception("Cleanup error"))
        
        await switch.async_turn_on()
        
        switch._manager.enable_interception.assert_called_once()
        switch._manager.disable_interception.assert_called_once()
        assert switch.is_on is False

    async def test_async_turn_off_interception_verification_success(self, switch):
        """Test turn off with successful interception verification."""
        switch._is_on = True
        switch._manager.disable_interception = AsyncMock()
        switch._manager.is_interception_enabled = False
        
        await switch.async_turn_off()
        
        switch._manager.disable_interception.assert_called_once()
        assert switch.is_on is False

    async def test_async_turn_off_interception_verification_failure(self, switch):
        """Test turn off with failed interception verification."""
        switch._is_on = True
        switch._manager.disable_interception = AsyncMock()
        switch._manager.is_interception_enabled = True  # Interception didn't actually stop
        
        await switch.async_turn_off()
        
        switch._manager.disable_interception.assert_called_once()
        assert switch.is_on is True  # Should keep current state

    async def test_async_will_remove_from_hass_cleanup(self, switch):
        """Test cleanup on entity removal."""
        switch._is_on = True
        switch._manager.disable_interception = AsyncMock()
        
        await switch.async_will_remove_from_hass()
        
        switch._manager.disable_interception.assert_called_once()

    async def test_async_will_remove_from_hass_cleanup_failure(self, switch):
        """Test cleanup failure on entity removal."""
        switch._is_on = True
        switch._manager.disable_interception = AsyncMock(side_effect=Exception("Cleanup error"))
        
        # Should not raise exception
        await switch.async_will_remove_from_hass()
        
        switch._manager.disable_interception.assert_called_once()

    async def test_async_will_remove_from_hass_not_enabled(self, switch):
        """Test entity removal when not enabled."""
        switch._is_on = False
        switch._manager.disable_interception = AsyncMock()
        
        await switch.async_will_remove_from_hass()
        
        switch._manager.disable_interception.assert_not_called()

    async def test_async_added_to_hass_no_previous_state(self, hass: HomeAssistant, switch):
        """Test entity added to hass with no previous state."""
        with patch.object(switch, "async_get_last_state", return_value=None):
            await switch.async_added_to_hass()
        
        assert switch.is_on is False
        switch._manager.enable_interception.assert_not_called()

    async def test_async_added_to_hass_previous_state_off(self, hass: HomeAssistant, switch):
        """Test entity added to hass with previous state off."""
        previous_state = State("switch.test", STATE_OFF)
        
        with patch.object(switch, "async_get_last_state", return_value=previous_state):
            await switch.async_added_to_hass()
        
        assert switch.is_on is False
        switch._manager.enable_interception.assert_not_called()

    async def test_async_added_to_hass_previous_state_on_success(self, hass: HomeAssistant, switch):
        """Test entity added to hass with previous state on - successful restoration."""
        previous_state = State("switch.test", STATE_ON)
        switch._manager.enable_interception = AsyncMock()
        
        with patch.object(switch, "async_get_last_state", return_value=previous_state):
            await switch.async_added_to_hass()
        
        assert switch.is_on is True
        switch._manager.enable_interception.assert_called_once()

    async def test_async_added_to_hass_previous_state_on_failure(self, hass: HomeAssistant, switch):
        """Test entity added to hass with previous state on - restoration failure."""
        previous_state = State("switch.test", STATE_ON)
        switch._manager.enable_interception = AsyncMock(side_effect=Exception("Test error"))
        
        with patch.object(switch, "async_get_last_state", return_value=previous_state):
            await switch.async_added_to_hass()
        
        assert switch.is_on is False  # Should be disabled on restoration failure
        switch._manager.enable_interception.assert_called_once()
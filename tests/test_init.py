"""Test the Simplified Adaptive Lighting integration setup and teardown."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.simplified_adaptive_lighting import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.simplified_adaptive_lighting.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        "name": "Test Adaptive Lighting",
        "lights": [
            {
                "entity_id": "light.test_light_1",
                "white_balance_offset": 0,
                "brightness_factor": 1.0,
            }
        ],
        "min_brightness": 1,
        "max_brightness": 255,
        "min_color_temp": 2000,
        "max_color_temp": 6500,
    }
    return entry


class TestAsyncSetup:
    """Test the async_setup function."""

    async def test_async_setup_returns_true(self, hass: HomeAssistant):
        """Test that async_setup returns True."""
        result = await async_setup(hass, {})
        assert result is True


class TestAsyncSetupEntry:
    """Test the async_setup_entry function."""

    @patch("custom_components.simplified_adaptive_lighting.AdaptiveLightingManager")
    async def test_setup_entry_success(
        self, mock_manager_class, hass: HomeAssistant, mock_config_entry
    ):
        """Test successful setup of config entry."""
        # Mock the manager
        mock_manager = AsyncMock()
        mock_manager.setup.return_value = True
        mock_manager_class.return_value = mock_manager

        # Mock the platform setup
        with patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward:
            mock_forward.return_value = True
            
            result = await async_setup_entry(hass, mock_config_entry)
            
            assert result is True
            
            # Verify manager was created and set up
            mock_manager_class.assert_called_once_with(hass, mock_config_entry.data)
            mock_manager.setup.assert_called_once()
            
            # Verify data was stored
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert "manager" in hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "config" in hass.data[DOMAIN][mock_config_entry.entry_id]
            
            # Verify platform setup was called
            mock_forward.assert_called_once_with(mock_config_entry, ["switch"])

    @patch("custom_components.simplified_adaptive_lighting.AdaptiveLightingManager")
    async def test_setup_entry_manager_setup_fails(
        self, mock_manager_class, hass: HomeAssistant, mock_config_entry
    ):
        """Test setup failure when manager setup fails."""
        # Mock the manager to fail setup
        mock_manager = AsyncMock()
        mock_manager.setup.return_value = False
        mock_manager_class.return_value = mock_manager

        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is False
        
        # Verify manager was created but setup failed
        mock_manager_class.assert_called_once_with(hass, mock_config_entry.data)
        mock_manager.setup.assert_called_once()
        
        # Verify no data was stored on failure
        assert DOMAIN not in hass.data or mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})

    @patch("custom_components.simplified_adaptive_lighting.AdaptiveLightingManager")
    async def test_setup_entry_manager_creation_fails(
        self, mock_manager_class, hass: HomeAssistant, mock_config_entry
    ):
        """Test setup failure when manager creation fails."""
        # Mock the manager creation to raise an exception
        mock_manager_class.side_effect = Exception("Manager creation failed")

        with pytest.raises(ConfigEntryNotReady, match="Failed to set up integration"):
            await async_setup_entry(hass, mock_config_entry)
        
        # Verify no data was stored on failure
        assert DOMAIN not in hass.data or mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})

    @patch("custom_components.simplified_adaptive_lighting.AdaptiveLightingManager")
    async def test_setup_entry_platform_setup_fails(
        self, mock_manager_class, hass: HomeAssistant, mock_config_entry
    ):
        """Test setup when platform setup fails."""
        # Mock the manager
        mock_manager = AsyncMock()
        mock_manager.setup.return_value = True
        mock_manager_class.return_value = mock_manager

        # Mock the platform setup to fail
        with patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward:
            mock_forward.side_effect = Exception("Platform setup failed")
            
            with pytest.raises(ConfigEntryNotReady, match="Failed to set up integration"):
                await async_setup_entry(hass, mock_config_entry)
            
            # Verify cleanup happened
            assert DOMAIN not in hass.data or mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})


class TestAsyncUnloadEntry:
    """Test the async_unload_entry function."""

    async def test_unload_entry_success(self, hass: HomeAssistant, mock_config_entry):
        """Test successful unload of config entry."""
        # Set up initial data
        mock_manager = AsyncMock()
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "manager": mock_manager,
                "config": mock_config_entry.data,
            }
        }

        # Mock the platform unload
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = True
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is True
            
            # Verify manager interception was disabled
            mock_manager.disable_interception.assert_called_once()
            
            # Verify platform unload was called
            mock_unload.assert_called_once_with(mock_config_entry, ["switch"])
            
            # Verify data was cleaned up
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_unload_entry_no_manager(self, hass: HomeAssistant, mock_config_entry):
        """Test unload when no manager is stored."""
        # Set up data without manager
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "config": mock_config_entry.data,
            }
        }

        # Mock the platform unload
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = True
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is True
            
            # Verify platform unload was called
            mock_unload.assert_called_once_with(mock_config_entry, ["switch"])
            
            # Verify data was cleaned up
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_unload_entry_platform_unload_fails(self, hass: HomeAssistant, mock_config_entry):
        """Test unload when platform unload fails."""
        # Set up initial data
        mock_manager = AsyncMock()
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "manager": mock_manager,
                "config": mock_config_entry.data,
            }
        }

        # Mock the platform unload to fail
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = False
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is False
            
            # Verify manager interception was still disabled
            mock_manager.disable_interception.assert_called_once()
            
            # Verify data was NOT cleaned up on failure
            assert mock_config_entry.entry_id in hass.data[DOMAIN]

    async def test_unload_entry_manager_disable_fails(self, hass: HomeAssistant, mock_config_entry):
        """Test unload when manager disable_interception fails."""
        # Set up initial data
        mock_manager = AsyncMock()
        mock_manager.disable_interception.side_effect = Exception("Disable failed")
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "manager": mock_manager,
                "config": mock_config_entry.data,
            }
        }

        # Mock the platform unload
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = True
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is False
            
            # Verify manager disable was attempted
            mock_manager.disable_interception.assert_called_once()
            
            # Verify data was cleaned up even on error
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_unload_entry_no_data(self, hass: HomeAssistant, mock_config_entry):
        """Test unload when no data is stored."""
        # Mock the platform unload
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = True
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is True
            
            # Verify platform unload was called
            mock_unload.assert_called_once_with(mock_config_entry, ["switch"])
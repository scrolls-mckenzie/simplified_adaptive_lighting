"""Data models for the Simplified Adaptive Lighting integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LightConfig:
    """Configuration for an individual light."""
    
    entity_id: str
    min_color_temp: int = 2000  # Minimum color temperature in Kelvin
    max_color_temp: int = 6500  # Maximum color temperature in Kelvin
    white_balance_offset: int = 0  # Kelvin offset for white balance correction
    brightness_factor: float = 1.0  # Multiplier for brightness adjustment
    enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "entity_id": self.entity_id,
            "min_color_temp": self.min_color_temp,
            "max_color_temp": self.max_color_temp,
            "white_balance_offset": self.white_balance_offset,
            "brightness_factor": self.brightness_factor,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LightConfig:
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            min_color_temp=data.get("min_color_temp", 2000),
            max_color_temp=data.get("max_color_temp", 6500),
            white_balance_offset=data.get("white_balance_offset", 0),
            brightness_factor=data.get("brightness_factor", 1.0),
            enabled=data.get("enabled", True),
        )


@dataclass
class AdaptiveSettings:
    """Adaptive lighting settings to apply to a light."""
    
    brightness: int  # 1-255
    color_temp_kelvin: int  # Color temperature in Kelvin
    transition: int = 1  # Transition time in seconds
    
    def to_service_data(self) -> dict[str, Any]:
        """Convert to service call data format."""
        return {
            "brightness": self.brightness,
            "kelvin": self.color_temp_kelvin,
            "transition": self.transition,
        }
"""Constants for the Simplified Adaptive Lighting integration."""

DOMAIN = "simplified_adaptive_lighting"

# Default configuration values
DEFAULT_MIN_BRIGHTNESS = 1
DEFAULT_MAX_BRIGHTNESS = 255
DEFAULT_MIN_COLOR_TEMP = 2000
DEFAULT_MAX_COLOR_TEMP = 6500
DEFAULT_WHITE_BALANCE_OFFSET = 0
DEFAULT_BRIGHTNESS_FACTOR = 1.0
DEFAULT_TRANSITION_TIME = 1

# Configuration keys
CONF_LIGHTS = "lights"
CONF_WHITE_BALANCE_OFFSET = "white_balance_offset"
CONF_BRIGHTNESS_FACTOR = "brightness_factor"
CONF_MIN_BRIGHTNESS = "min_brightness"
CONF_MAX_BRIGHTNESS = "max_brightness"
CONF_MIN_COLOR_TEMP = "min_color_temp"
CONF_MAX_COLOR_TEMP = "max_color_temp"

# Service names
SERVICE_LIGHT_TURN_ON = "light.turn_on"
SERVICE_LIGHT_TOGGLE = "light.toggle"

# Attributes
ATTR_BRIGHTNESS = "brightness"
ATTR_COLOR_TEMP = "color_temp"
ATTR_KELVIN = "kelvin"
ATTR_TRANSITION = "transition"
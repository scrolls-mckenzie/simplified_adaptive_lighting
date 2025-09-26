# Simplified Adaptive Lighting

A streamlined adaptive lighting integration for Home Assistant that automatically adjusts light brightness and color temperature based on time of day.

## Features

- **Seamless Integration**: Works with any control source (Home Assistant UI, HomeKit, automations, etc.)
- **Per-Light Configuration**: Individual white balance and brightness adjustments for each light
- **Time-Based Adaptation**: Automatic brightness and color temperature adjustments throughout the day
- **Simple Setup**: Easy configuration through Home Assistant's UI

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the "+" button in the bottom right
4. Search for "Simplified Adaptive Lighting"
5. Click "Download"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `simplified_adaptive_lighting` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Simplified Adaptive Lighting"
4. Follow the configuration wizard:
   - Enter a name for your adaptive lighting setup
   - Select the lights you want to control
   - Adjust white balance settings for each light (optional)

## Usage

Once configured, the integration creates a switch entity that controls adaptive lighting:

- **Turn On**: Enables adaptive lighting for selected lights
- **Turn Off**: Disables adaptive lighting (lights work normally)

When adaptive lighting is enabled:
- Lights automatically adjust brightness and color temperature when turned on
- Settings are applied regardless of how lights are controlled (UI, voice, automation)
- Each light uses its individual white balance corrections

## White Balance Adjustment

Different light manufacturers may have slightly different color temperatures. Use the white balance offset to make all your lights appear consistent:

- **Positive values**: Make lights cooler (more blue)
- **Negative values**: Make lights warmer (more yellow)
- **Range**: -1000K to +1000K

## Brightness Factor

Adjust the overall brightness level for individual lights:

- **Values > 1.0**: Make lights brighter
- **Values < 1.0**: Make lights dimmer
- **Range**: 0.1x to 2.0x

## Troubleshooting

### Lights Not Responding to Adaptive Settings

1. Ensure the lights are selected in the integration configuration
2. Verify the adaptive lighting switch is turned on
3. Check that lights support both brightness and color temperature control

### Integration Not Appearing

1. Ensure you've restarted Home Assistant after installation
2. Check the Home Assistant logs for any error messages
3. Verify the integration files are in the correct directory

### Performance Issues

The integration is designed to add minimal latency (< 100ms) to light commands. If you experience delays:

1. Check your Home Assistant system resources
2. Reduce the number of lights under adaptive control
3. Check for conflicts with other lighting integrations

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Report an issue](https://github.com/user/simplified-adaptive-lighting/issues)
- Home Assistant Community: [Discussion thread](https://community.home-assistant.io)

## Version History

### 1.0.0
- Initial release
- Basic adaptive lighting functionality
- Per-light white balance configuration
- HACS compatibility
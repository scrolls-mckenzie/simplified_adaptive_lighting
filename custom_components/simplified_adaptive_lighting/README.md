# Simplified Adaptive Lighting Integration

## Light Platform

The light platform creates independent adaptive light entities that wrap existing Home Assistant light entities with automatic color temperature adjustment based on time of day.

### Features

- **Independent Entities**: Creates new light entities (e.g., "Adaptive Living Room Light") that can be controlled independently
- **Automatic Color Temperature**: Calculates appropriate color temperature based on Home Assistant's sun data
- **User Control Preservation**: Maintains user-specified brightness while adapting color temperature
- **HomeKit Compatible**: Designed to be shared to HomeKit through Homebridge as primary control entities
- **Per-Light Configuration**: Supports individual color temperature ranges and corrections per light

### Entity Naming

Adaptive light entities are named using the following scheme:
- **Entity ID**: `light.simplified_adaptive_lighting_[entry_id]_[target_light_name]`
- **Friendly Name**: `Adaptive [Target Light Friendly Name]` or `Adaptive [Formatted Target Name]`

Examples:
- Target: `light.living_room` → Adaptive: `Adaptive Living Room`
- Target: `light.bedroom_lamp` → Adaptive: `Adaptive Bedroom Lamp`

### Behavior

1. **Turn On**: When turned on, the adaptive light:
   - Calculates appropriate color temperature based on current time and sun position
   - Applies user-specified brightness (if provided) or uses adaptive brightness
   - Sends commands to the underlying physical light entity
   - Respects per-light color temperature ranges and corrections

2. **Turn Off**: Directly turns off the underlying physical light

3. **State Synchronization**: Reflects the state of the underlying light while showing adaptive color temperature

### Configuration

Each adaptive light entity is configured with:
- `entity_id`: The target light entity to wrap
- `white_balance_offset`: Kelvin offset for color temperature correction
- `brightness_factor`: Multiplier for brightness adjustment
- `enabled`: Whether adaptive functionality is enabled

### Error Handling

- **Target Light Unavailable**: Shows adaptive light as unavailable
- **Calculation Errors**: Falls back to original user commands if adaptive calculation fails
- **Invalid Entities**: Skips creation of adaptive entities for non-existent or non-light entities

### Testing

The light platform includes comprehensive tests covering:
- Entity creation and naming
- Light validation
- Adaptive settings application logic
- Error handling scenarios

Run tests with: `python -m pytest tests/test_light_platform_basic.py -v`
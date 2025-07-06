# Indoor Sun Brightness & RGB

Home Assistant custom component that fetches JPEG frames from a Frigate camera and calculates brightness and RGB values to create ambient lighting that matches the sky conditions.

[![Add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository_url=https%3A%2F%2Fgithub.com%2Flnxd%2Fhass-indoor-sun&category=integration)

## Features

- **Brightness Sensor**: Calculates brightness percentage using the luminance formula: `Y = 0.2126*R + 0.7152*G + 0.0722*B`
- **RGB Sensor**: Provides average RGB values from the camera frame
- **Async Operation**: Uses modern Home Assistant patterns with `DataUpdateCoordinator`
- **Frigate Integration**: Fetches frames from Frigate's JPEG endpoint (`/api/<camera>/latest.jpg`)
- **Configurable Update Interval**: Default 60 seconds, customizable per camera

## Installation

1. Clone this repository into your Home Assistant `custom_components` directory:
   ```bash
   cd /path/to/homeassistant/custom_components/
   git clone https://github.com/lnxd/hass-indoor-sun.git
   ```

2. Restart Home Assistant

3. Add the integration through the UI or via YAML configuration

## Configuration

### YAML Configuration

Add to your `configuration.yaml`:

```yaml
hass-indoor-sun:
  - base_url: http://192.168.1.30:5000
    camera: driveway
    scan_interval: 60
  - base_url: http://192.168.1.30:5000
    camera: backyard
    scan_interval: 30
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `base_url` | string | Yes | - | Base URL of your Frigate server |
| `camera` | string | Yes | - | Name of the Frigate camera |
| `scan_interval` | integer | No | 60 | Update interval in seconds |

## Sensors

The component creates two sensors for each configured camera:

### `sensor.sun_brightness`
- **Unit**: `%`
- **Device Class**: `illuminance`
- **State**: Brightness percentage (0-100)
- **Attributes**:
  - `camera`: Camera name
  - `base_url`: Frigate server URL
  - `r`, `g`, `b`: Individual RGB values

### `sensor.sun_rgb`
- **State**: RGB string format "R, G, B"
- **Attributes**:
  - `camera`: Camera name
  - `base_url`: Frigate server URL
  - `r`, `g`, `b`: Individual RGB values
  - `brightness`: Brightness percentage

## Automation Examples

### Sync Living Room Lights with Sky

```yaml
alias: Sync lights with sky
trigger:
  - platform: time_pattern
    minutes: "/1"
action:
  - service: light.turn_on
    target:
      area_id: living_room
    data:
      rgb_color: >
        {{ state_attr('sensor.sun_rgb', 'r') }},{{ state_attr('sensor.sun_rgb', 'g') }},{{ state_attr('sensor.sun_rgb', 'b') }}
      brightness_pct: "{{ states('sensor.sun_brightness') | int }}"
```

### Adjust Brightness Based on Sky Conditions

```yaml
alias: Adjust brightness based on sky
trigger:
  - platform: state
    entity_id: sensor.sun_brightness
action:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: sensor.sun_brightness
            below: 20
        sequence:
          - service: light.turn_on
            target:
              entity_id: light.outdoor_lights
            data:
              brightness_pct: 100
      - conditions:
          - condition: numeric_state
            entity_id: sensor.sun_brightness
            above: 80
        sequence:
          - service: light.turn_off
            target:
              entity_id: light.outdoor_lights
    default:
      - service: light.turn_on
        target:
          entity_id: light.outdoor_lights
        data:
          brightness_pct: "{{ 100 - (states('sensor.sun_brightness') | int) }}"
```

### Notification on Dramatic Sky Changes

```yaml
alias: Notify on dramatic sky changes
trigger:
  - platform: state
    entity_id: sensor.sun_brightness
condition:
  - condition: template
    value_template: >
      {{ (trigger.to_state.state | int) - (trigger.from_state.state | int) | abs > 20 }}
action:
  - service: notify.mobile_app
    data:
      title: "Sky Conditions Changed"
      message: >
        Brightness changed from {{ trigger.from_state.state }}% to {{ trigger.to_state.state }}%
```

## Technical Details

### Dependencies
- **Pillow**: For image processing
- **aiohttp**: For async HTTP requests (provided by Home Assistant)
- **async_timeout**: For request timeouts (provided by Home Assistant)

### Image Processing
- Fetches JPEG frames from Frigate's REST API
- Processes images asynchronously using Home Assistant's executor
- Calculates average RGB values across all pixels
- Uses the standard luminance formula for brightness calculation

### Performance
- Images are processed in a separate thread to avoid blocking the event loop
- 10-second timeout for HTTP requests
- Configurable update intervals to balance accuracy vs. performance

## Troubleshooting

### Common Issues

1. **Sensor shows "unavailable"**
   - Check that Frigate server is accessible
   - Verify camera name exists in Frigate
   - Check Home Assistant logs for detailed error messages

2. **Slow updates**
   - Reduce scan_interval for more frequent updates
   - Check network latency to Frigate server
   - Monitor Home Assistant CPU usage

3. **Memory usage**
   - Large images may consume significant memory
   - Consider reducing camera resolution in Frigate if needed

### Debugging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.hass-indoor-sun: debug
```

## Development

Built with modern Home Assistant patterns:
- Uses `DataUpdateCoordinator` for efficient data management
- Implements proper async/await patterns
- Follows Home Assistant entity conventions
- Includes comprehensive error handling

## License

This project is licensed under the MIT License.
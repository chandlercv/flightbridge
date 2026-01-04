# Flight Panel LED Control

Flightbridge now supports controlling the Saitek/Logitech Flight Switch Panel LEDs (N, L, R position lights).

## Overview

The Flight Panel has three position indicator lights that can be controlled via HID feature reports:
- **N Light** (Nose/Center position indicator) - Red by default
- **L Light** (Left position indicator) - Red by default  
- **R Light** (Right position indicator) - Yellow by default

These lights are typically used to indicate aircraft landing gear position in flight simulators.

## How It Works

1. The LED controller queries the Flight Panel's current state on startup
2. LED bits are identified in the HID feature report:
   - **Byte 1, Bit 0 (0x01)** = N Light
   - **Byte 2, Bit 0 (0x01)** = L Light
3. When mapping produces LED commands, the controller modifies the feature report and sends it to the device
4. The Flight Panel hardware updates the LED states accordingly

## YAML Profile Syntax

In your mapping profile, use the `led:` prefix to control LEDs:

```yaml
bindings:
  # Control landing gear lights together (common use case)
  - input: "x55.button.10"
    target: "led:landing_gear"
  
  # Control individual lights
  - input: "x55.button.11"
    target: "led:n_light"
  
  - input: "x55.button.12"
    target: "led:l_light"
  
  # Multi-input example: light on when both switches are on
  - inputs:
      - "flightpanel.switch.0"
      - "flightpanel.switch.1"
    target: "led:landing_gear"
    props:
      logic: "and"
```

## Available LED Targets

| Target | Description | Behavior |
|--------|-------------|----------|
| `led:n_light` | N position light | ON when input is true, OFF when false |
| `led:l_light` | L position light | ON when input is true, OFF when false |
| `led:landing_gear` | Combined N+L lights | Convenience target for landing gear (controls both N and L) |

## Examples

### Simple Button Toggle
```yaml
- input: "x55.button.10"
  target: "led:landing_gear"
```
Button 10 controls landing gear lights. While pressed, lights are ON.

### Multi-Input Landing Gear
```yaml
- inputs:
    - "flightpanel.switch.0"  # Up position
    - "flightpanel.switch.1"  # Down position
  target: "led:landing_gear"
  props:
    logic: "all_same"
```
Lights are ON when both switches are in the same state (both ON or both OFF).

### Independent Lights
```yaml
- input: "flightpanel.switch.3"
  target: "led:n_light"
  
- input: "flightpanel.switch.4"
  target: "led:l_light"
```
Switch 3 controls the N light, Switch 4 controls the L light independently.

## Implementation Details

### LED Controller Class

The `FlightPanelLEDControl` class in [devices/flight_panel_leds.py](devices/flight_panel_leds.py) handles:

```python
led_controller = FlightPanelLEDControl()
led_controller.connect()           # Open device connection
led_controller.set_n_light(True)   # Turn N light ON
led_controller.set_l_light(False)  # Turn L light OFF
led_controller.set_landing_gear(True)  # Shortcut for both lights
led_controller.disconnect()        # Clean up
```

### Integration with VJoy

The LED commands are integrated into the `VJoyCommand` object and processed in the mapper's output loop. Each cycle, any LED state changes are applied to the hardware immediately.

## Logging

Enable DEBUG logging to see LED control activity:

```bash
python app.py --profile config/mappings/your_profile.yaml --log-level DEBUG --debug-modules panel
```

Output will show LED state changes:
```
DEBUG:flightbridge.flight_panel_leds:N light: ON
DEBUG:flightbridge.flight_panel_leds:L light: OFF
```

## Troubleshooting

### LEDs not responding
1. Check that the Flight Panel is detected:
   - Look for "Flight Panel LED control connected" message on startup
   - Run: `python tests/test_flight_panel_capabilities.py`

2. Verify the YAML profile syntax is correct:
   - Use `led:` prefix (not `button:` or `axis:`)
   - Valid targets: `landing_gear`, `n_light`, `l_light`

3. Check your input binding source:
   - Make sure the input (e.g., `x55.button.10`) is configured correctly
   - You can test inputs are being read with: `--log-level DEBUG --debug-modules panel`

### Device not found
If the Flight Panel is not detected at startup:
- Ensure the device is plugged in
- Check Windows Device Manager for "Saitek Pro Flight Switch Panel"
- Run the device discovery test: `python tests/test_flight_panel_capabilities.py`

## Hardware Details

The Saitek Pro Flight Switch Panel uses:
- **VID:PID:** `06a3:0d67`
- **Interface:** HID (Human Interface Device)
- **Report Format:** Feature report (ID 0) for state queries and LED control

LED control is performed via:
1. Reading current state: `get_feature_report(0, 64)`
2. Modifying LED bits in the returned data
3. Sending back: `send_feature_report(modified_data)`

See [tests/test_flight_panel_leds.py](tests/test_flight_panel_leds.py) for detailed hardware testing code.

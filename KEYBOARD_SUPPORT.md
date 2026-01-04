# Keyboard Support in Flightbridge

Flightbridge now supports sending keyboard keystrokes in addition to vJoy commands. This allows you to map flight hardware buttons and switches to keyboard keys.

## Installation

Make sure `pynput` is installed. If you haven't already, run:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Syntax

In your YAML mapping profile, use `key:` as the target prefix instead of `button:` or `axis:`:

```yaml
- input: "x55.button.0"
  target: "key:w"  # Send 'W' key when button is pressed
```

### Direct Mode (Sustained Keys)

By default, keyboard mappings use **direct mode**, which means the key stays pressed as long as the physical button is held down:

```yaml
- input: "flightpanel.switch.0"
  target: "key:a"
  props:
    mode: "direct"
```

When the switch/button goes ON, the 'A' key is pressed. When it goes OFF, the key is released.

### Toggle Mode (Momentary Pulse)

For momentary keystrokes (like sending a command), use **toggle mode**:

```yaml
- input: "flightpanel.switch.1"
  target: "key:space"
  props:
    mode: "toggle"
    pulse_ms: 100  # Key is pressed for 100ms then released
    trigger: "on_press"  # Options: "on_change", "on_press", "on_release"
```

Options:
- `pulse_ms`: How long to hold the key down (milliseconds)
- `trigger`: When to trigger the pulse:
  - `"on_change"`: When the button state changes (default)
  - `"on_press"`: Only when button is pressed (goes from OFF to ON)
  - `"on_release"`: Only when button is released (goes from ON to OFF)

### Multi-Button Logic

You can combine multiple inputs with logical conditions:

```yaml
- inputs:
    - "flightpanel.switch.0"
    - "flightpanel.switch.1"
  target: "key:w"
  props:
    mode: "toggle"
    logic: "all_same"  # Fire when ALL inputs are true OR ALL inputs are false
    pulse_ms: 50
```

## Supported Key Names

### Named Keys
- `space`, `enter`, `return`
- `tab`, `backspace`, `delete`, `insert`
- `home`, `end`, `pageup`, `pagedown`
- `up`, `down`, `left`, `right`
- `escape`, `esc`
- `shift`, `shift_l`, `shift_r`
- `ctrl`, `ctrl_l`, `ctrl_r`, `control`
- `alt`, `alt_l`, `alt_r`
- `cmd`, `cmd_l`, `cmd_r`, `win`, `windows`
- `f1` through `f12` (function keys)

### Single Character Keys
You can also use single characters directly:
- Alphanumeric: `a`, `b`, `c`, ... `z`, `0`, `1`, ... `9`
- Symbols: `.`, `,`, `/`, `\`, etc.

## Examples

### Sustained Movement Key
```yaml
- input: "flightpanel.switch.0"
  target: "key:w"  # Forward movement in most games
  props:
    mode: "direct"
```

### Momentary Action Key
```yaml
- input: "ch_throttle.button.0"
  target: "key:space"  # Jump, confirm, etc.
  props:
    mode: "toggle"
    pulse_ms: 100
    trigger: "on_press"
```

### Complex Multi-Switch Combo
```yaml
- inputs:
    - "flightpanel.switch.10"
    - "flightpanel.switch.11"
  target: "key:ctrl"
  props:
    mode: "direct"
    logic: "and"  # Send Ctrl when BOTH switches are ON
```

## Mixing vJoy and Keyboard

You can use both vJoy and keyboard targets in the same profile:

```yaml
bindings:
  # vJoy joystick axes
  - input: "x55.axes.0"
    target: "axis:AXIS_X"
  
  # vJoy buttons
  - input: "x55.button.0"
    target: "button:1"
  
  # Keyboard keys
  - input: "x55.button.1"
    target: "key:w"
  
  # Flight panel switch to vJoy
  - input: "flightpanel.switch.0"
    target: "button:27"
    props:
      mode: "toggle"
      pulse_ms: 100
  
  # Flight panel switch to keyboard
  - input: "flightpanel.switch.1"
    target: "key:space"
    props:
      mode: "toggle"
      pulse_ms: 50
```

## Troubleshooting

### Keys not being sent
1. Make sure `pynput` is installed: `pip install pynput`
2. Check the logs for keyboard errors:
   ```bash
   python app.py --profile allegiance.yaml --log-level DEBUG --debug-modules vjoy
   ```
3. On Windows, make sure no administrator-required application has exclusive keyboard focus
4. On macOS, you may need to grant accessibility permissions to the Python process

### Unknown key name warning
If you see `WARNING: Unknown key name: xxx`, check that the key name is in the supported list above or use a single character instead.

### Keys stick/don't release
This can happen if the application crashes before releasing keys. Run:
- Windows: Press and release all modifier keys (Shift, Ctrl, Alt) to clear the stuck state
- macOS/Linux: Same approach or restart the input system

## Implementation Details

- Keyboard support uses the `pynput` library for cross-platform compatibility
- Keys are tracked in state, so state transitions trigger press/release
- On application shutdown, all currently pressed keys are automatically released
- Keyboard commands are sent before vJoy updates in each cycle (no conflicts)

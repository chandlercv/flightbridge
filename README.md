# flightbridge

Bridge inputs from Logitech flight panels and Saitek X-55 (DirectInput) to vJoy using Python.

Quickstart:
- Install vJoy via winget (64-bit) and create a virtual device (axes, buttons, POV):
    winget install ShaulEizikovich.vJoyDeviceDriver
    # If the DLL is not at the default path, update it in vjoy/output.py.
- Install hidhide `winget install Nefarius.HidHide`
- Install Python deps (recommended):
  create venv
  pip install requirements.txt
- Run:
  python app.py --profile config/mappings/elite_dangerous.yaml

This repo contains initial scaffolding (readers, mapper, vjoy output) — more implementation coming.

## Command-Line Options

Run `app.py` (or the packaged EXE) with these switches:

- `--profile <path>`: Required. YAML mapping profile to load.
- `--vjoy-id <int>`: Primary vJoy device id (default: 1).
- `--vjoy-devices <int...>`: List of vJoy device IDs (e.g., `1 2` for 64 buttons). Overrides `--vjoy-id`.
- `--hz <int>`: vJoy update frequency (default: 60).
- `--log-level <DEBUG|INFO|WARNING|ERROR|CRITICAL>`: Global log level (default: INFO).
- `--log-format <format>`: Python logging format string.
- `--debug-modules <module...>`: Set specific module loggers to DEBUG.
  - Valid module names: `panel`, `x55`, `x52`, `throttle`, `vjoy`, `mapper`.
- `--debug-keys`: Console-only keyboard press/release logging (filters out vJoy axis/POV chatter).

### Examples

```bash
python app.py --profile config/mappings/elite.yaml
```

```bash
python app.py --profile config/mappings/elite.yaml --debug-keys
```

```bash
python app.py --profile config/mappings/elite.yaml --log-level DEBUG --debug-modules mapper vjoy
```

## Available Inputs (Switches/Buttons)

The mapper accepts device inputs using these patterns:

- **Flight Switch Panel (Saitek/Logitech)**
  - `flightpanel.switch.N` and `flightpanel.button.N` are aliases to the same underlying switch bit.
  - Valid index range is `0..19`. Unused indices stay false; actual physical mapping can vary by unit.
  - To discover which physical switch maps to which index, use [tests/test_flight_panel_capabilities.py](tests/test_flight_panel_capabilities.py) or [tests/test_button_capture.py](tests/test_button_capture.py).

- **X-55 (DirectInput)**
  - `x55.button.N` where `N` is `0..(num_buttons-1)`
  - `x55.axes.N` where `N` is `0..(num_axes-1)`
  - `x55.hat.N` where `N` is `0..(num_hats-1)`
  - To inspect the counts and live values, use [tests/test_x55_dump.py](tests/test_x55_dump.py) or [tests/test_buttons_simple.py](tests/test_buttons_simple.py).

- **X-52 (DirectInput)**
  - `x52.button.N` where `N` is `0..(num_buttons-1)`
  - `x52.axes.N` where `N` is `0..(num_axes-1)`
  - `x52.hat.N` where `N` is `0..(num_hats-1)`
  - To inspect the counts and live values, use [tests/test_x55_dump.py](tests/test_x55_dump.py).

- **CH Throttle (DirectInput)**
  - `ch_throttle.axes.0` (throttle axis)
  - `ch_throttle.button.N` where `N` is `0..11`
  - To verify button indices, use [tests/test_ch_throttle_dump.py](tests/test_ch_throttle_dump.py).

## Mapping Props: `mode` and `logic`

Bindings in YAML can include `props` to control how inputs drive outputs. The mapper currently supports:

- `mode`: How the output is driven.
  - `direct`: Output follows the input state continuously (default).
  - `toggle`: Output is pulsed briefly when the input condition becomes true. Use with `pulse_ms` and, for flight panel single inputs, `trigger`.

- `logic`: How multiple inputs are combined (used only when a binding has `inputs` instead of `input`).
  - `and`: Condition is true when all inputs are true.
  - `all_same`: Condition is true when all inputs are true or all inputs are false.

Additional supporting props:
- `pulse_ms`: Pulse duration in milliseconds for `toggle` mode (default 100ms).
- `trigger`: For flight panel `switch`/`button` single-input bindings in `toggle` mode: when to pulse — `on_change` (default), `on_press` (only when going true), or `on_release` (only when going false).
- `unless`: Optional top-level binding key listing inputs that must be false for the binding to activate (works for multi-input bindings in both `direct` and `toggle`).

### Examples

1) Single input (flight panel switch) pulsing a key only when switched on:

```yaml
- input: "flightpanel.switch.18"
  target: "key:control key:5"
  props:
    mode: "toggle"
    pulse_ms: 100
    trigger: on_press
```

2) Two inputs must both be pressed to pulse a key:

```yaml
- inputs:
    - "x55.button.10"
    - "flightpanel.button.13"
  target: "key:t"
  props:
    mode: "toggle"
    logic: "and"
    pulse_ms: 100
```

In `toggle` mode with multiple inputs, the mapper pulses only on transitions from false → true of the combined condition (no pulse when the condition becomes false).

3) Pulse when two switches are in the same state (both on or both off):

```yaml
- inputs:
    - "flightpanel.switch.0"
    - "flightpanel.switch.1"
  target: "key:control key:7"
  props:
    mode: "toggle"
    logic: "all_same"
    pulse_ms: 100
```

For `direct` mode with multiple inputs, the output stays true as long as the combined condition (`and` or `all_same`) evaluates true.

4) Gate an action unless another input is active:

```yaml
- inputs:
    - "x55.button.10"
    - "flightpanel.button.14"
  unless:
    - "flightpanel.button.6"   # Only activate when .6 is false
  target: "key:f"
  props:
    mode: "toggle"
    logic: "and"
    pulse_ms: 100

- inputs:
    - "x55.button.10"
    - "flightpanel.button.14"
    - "flightpanel.button.6"
  target: "key:f9"
  props:
    mode: "toggle"
    logic: "and"
    pulse_ms: 100
```

With the above, pressing `x55.button.10` while `flightpanel.button.14` is held will pulse `f` when `.6` is off, and `f9` when `.6` is on.

Notes:
- `mode`/`trigger` for single-input `toggle` are implemented for flight panel `switch` and `button`. Other single-input devices map in `direct` mode.
- Axis props (`invert`, `scale`) continue to apply to axis bindings as shown in the sample profiles.

"""Entry point for flightbridge

Starts device readers, mapping, and vJoy output loop using a chosen profile.
"""
import argparse
import logging
import signal
import threading
import time
import os

from mapper import Mapper
from vjoy.output import VJoyOutput
from devices.x55_directinput import X55Reader
from devices.x52_directinput import X52Reader
from devices.flight_panel import FlightPanelReader
from devices.flight_panel_leds import FlightPanelLEDControl
from devices.ch_throttle import CHThrottleReader
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

LOG = logging.getLogger("flightbridge")
STATE_LOG = logging.getLogger("flightbridge.state")


def main():
    parser = argparse.ArgumentParser(description="Flightbridge: X55 + FlightPanel + CH Throttle → vJoy")
    parser.add_argument("--profile", required=True, help="YAML mapping profile")
    parser.add_argument("--vjoy-id", type=int, default=1, help="Primary vJoy device id")
    parser.add_argument("--vjoy-devices", type=int, nargs="+", default=None, 
                        help="List of vJoy device IDs (e.g., 1 2 for 64 buttons). Overrides --vjoy-id")
    parser.add_argument("--hz", type=int, default=60, help="vJoy update frequency")
    parser.add_argument("--log-level", default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level (default: INFO)")
    parser.add_argument("--log-format", default="%(levelname)s:%(name)s:%(message)s",
                        help="Logging format string (default: %(levelname)s:%(name)s:%(message)s)")
    parser.add_argument("--debug-modules", nargs="*", default=[],
                        help="Modules to set to DEBUG level (e.g., 'panel', 'x55', 'throttle', 'vjoy', 'mapper')")
    parser.add_argument("--debug-keys", action="store_true",
                        help="Enable DEBUG logging for key presses only (vjoy module), without HID input logs")
    parser.add_argument("--debug-changes", action="store_true",
                        help="Log only input state changes from previous state (suppresses raw state spam)")
    parser.add_argument("--debug-axis-deadzone", type=float, default=0.01,
                        help="Minimum axis delta to log in --debug-changes (default: 0.01)")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format=args.log_format)
    
    # Set DEBUG level for specific modules if requested
    module_map = {
        "panel": "flightbridge.panel",
        "x55": "flightbridge.x55",
        "x52": "flightbridge.x52",
        "throttle": "flightbridge.ch_throttle",
        "vjoy": "flightbridge.vjoy",
        "mapper": "flightbridge.mapper",
        "state": "flightbridge.state",
    }
    for module in args.debug_modules:
        logger_name = module_map.get(module, f"flightbridge.{module}")
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    if args.debug_changes:
        logging.getLogger().setLevel(logging.DEBUG)

        class _SuppressRawStateFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                message = record.getMessage()
                if "raw state ->" in message:
                    return False
                if message.startswith("FlightPanel: emit"):
                    return False
                return True

        for logger_name in ("flightbridge.x55", "flightbridge.x52", "flightbridge.ch_throttle", "flightbridge.panel"):
            logging.getLogger(logger_name).addFilter(_SuppressRawStateFilter())

        class _SuppressMapperVjoyNoise(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                message = record.getMessage()
                if message.startswith("set axis "):
                    return False
                if message.startswith("set pov "):
                    return False
                if message.startswith("mapped hat "):
                    return False
                if message.startswith("mapped state ->"):
                    return False
                return True

        logging.getLogger("flightbridge.vjoy").addFilter(_SuppressMapperVjoyNoise())
        logging.getLogger("flightbridge.mapper").addFilter(_SuppressMapperVjoyNoise())

    if args.debug_keys:
        vjoy_logger = logging.getLogger("flightbridge.vjoy")
        vjoy_logger.setLevel(logging.DEBUG)
        vjoy_logger.propagate = False
        vjoy_logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(args.log_format))

        class _KeyDebugFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                if record.levelno >= logging.INFO:
                    return True
                message = record.getMessage()
                return (
                    message.startswith("keyboard:")
                    or "Unknown key name" in message
                    or "failed to send keyboard" in message
                    or "failed to release keyboard" in message
                )

        handler.addFilter(_KeyDebugFilter())
        vjoy_logger.addHandler(handler)

    mapper = Mapper.load_profile(args.profile)
    mapper_lock = threading.Lock()

    def reload_mapper():
        """Reload the mapping profile and atomically swap the active mapper."""
        try:
            new_mapper = Mapper.load_profile(args.profile)
        except Exception as e:
            LOG.error("Config reload failed: %s", e)
            return
        with mapper_lock:
            nonlocal mapper
            mapper = new_mapper
        LOG.info("Config reloaded from %s", args.profile)

    class _ConfigHandler(FileSystemEventHandler):
        def __init__(self, target_path, on_reload, debounce_sec=0.3):
            self._target = os.path.abspath(target_path)
            self._last = 0.0
            self._on_reload = on_reload
            self._debounce = debounce_sec

        def on_modified(self, event):
            src = getattr(event, "src_path", "")
            if os.path.abspath(src) != self._target:
                return
            now = time.monotonic()
            if now - self._last < self._debounce:
                return
            self._last = now
            self._on_reload()

    def start_config_watcher(path):
        watch_dir = os.path.dirname(os.path.abspath(path)) or "."
        handler = _ConfigHandler(path, reload_mapper)
        obs = Observer()
        obs.schedule(handler, path=watch_dir, recursive=False)
        obs.start()
        LOG.info("Watching %s for changes", path)
        return obs

    # Determine vJoy devices: CLI overrides profile, else default single
    profile_vjoy_devices = mapper.profile.get("vjoy_devices") if hasattr(mapper, "profile") else None
    if args.vjoy_devices:
        vjoy_devices = args.vjoy_devices
    elif profile_vjoy_devices:
        vjoy_devices = profile_vjoy_devices
    else:
        vjoy_devices = None

    # Initialize LED controller for Flight Panel
    led_controller = FlightPanelLEDControl()
    if not led_controller.connect():
        LOG.warning("Flight Panel LED control not available (device not found)")
        led_controller = None

    # Support multiple vJoy devices for >32 buttons
    if vjoy_devices:
        vjoy = VJoyOutput(hz=args.hz, device_ids=vjoy_devices, led_controller=led_controller)
    else:
        vjoy = VJoyOutput(args.vjoy_id, hz=args.hz, led_controller=led_controller)

    def _extract_devices(profile: dict):
        bindings = profile.get("bindings", []) if isinstance(profile, dict) else []
        devices = set()
        for binding in bindings:
            src = binding.get("input")
            if src:
                devices.add(src.split(".", 1)[0])
            for item in binding.get("inputs", []) or []:
                if item:
                    devices.add(item.split(".", 1)[0])
        return {d for d in devices if d}

    required_devices = _extract_devices(mapper.profile)
    if not required_devices:
        required_devices = {"x55", "x52", "flightpanel", "ch_throttle"}

    readers = {}
    if "x55" in required_devices:
        readers["x55"] = X55Reader()
    if "x52" in required_devices:
        readers["x52"] = X52Reader()
    if "flightpanel" in required_devices:
        readers["flightpanel"] = FlightPanelReader()
    if "ch_throttle" in required_devices:
        readers["ch_throttle"] = CHThrottleReader()

    LOG.info("Active device readers: %s", ", ".join(sorted(readers.keys())))

    stop_event = threading.Event()
    state_lock = threading.Lock()
    accumulated_state = {}  # Store merged state from all devices
    pulse_thread = None

    def _diff_map(prev_map, curr_map, *, min_delta: float = 0.0):
        changes = {}
        all_keys = set(prev_map.keys()) | set(curr_map.keys())
        for key in sorted(all_keys):
            prev_val = prev_map.get(key)
            curr_val = curr_map.get(key)
            if prev_val != curr_val:
                if min_delta and isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
                    if abs(curr_val - prev_val) < min_delta:
                        continue
                changes[key] = curr_val
        return changes

    def _diff_device_state(prev_state, curr_state, *, axis_deadzone: float = 0.0):
        if prev_state is None:
            return {
                "axes": dict(curr_state.get("axes", {})),
                "buttons": dict(curr_state.get("buttons", {})),
                "hats": dict(curr_state.get("hats", {})),
            }
        axes_changes = _diff_map(prev_state.get("axes", {}), curr_state.get("axes", {}), min_delta=axis_deadzone)
        button_changes = _diff_map(prev_state.get("buttons", {}), curr_state.get("buttons", {}))
        hat_changes = _diff_map(prev_state.get("hats", {}), curr_state.get("hats", {}))
        diff = {}
        if axes_changes:
            diff["axes"] = axes_changes
        if button_changes:
            diff["buttons"] = button_changes
        if hat_changes:
            diff["hats"] = hat_changes
        return diff or None

    def on_state(state):
        with state_lock:
            # Merge this device's state into accumulated state
            device_name = state.get("device")
            prev_state = accumulated_state.get(device_name)
            accumulated_state[device_name] = state
        if args.debug_changes:
            diff = _diff_device_state(prev_state, state, axis_deadzone=args.debug_axis_deadzone)
            if diff:
                STATE_LOG.debug("input change %s -> %s", device_name, diff)
        # Map the full accumulated state using the current mapper atomically
        with mapper_lock:
            cmd = mapper.map_state_to_vjoy_full(accumulated_state)
        vjoy.apply(cmd)

    def pulse_loop():
        # Drives pulse timers even when no new device events arrive
        tick = 1.0 / float(args.hz)
        while not stop_event.is_set():
            with mapper_lock:
                active_pulses = mapper.has_active_pulses()
                next_expiration = mapper.next_pulse_expiration()

            if not active_pulses:
                time.sleep(tick)
                continue

            with state_lock:
                state_snapshot = dict(accumulated_state)

            with mapper_lock:
                cmd = mapper.map_state_to_vjoy_full(state_snapshot)

            vjoy.apply(cmd)

            if next_expiration:
                sleep_for = max(0.001, min(tick, next_expiration - time.time()))
            else:
                sleep_for = tick
            time.sleep(sleep_for)

    for reader in readers.values():
        reader.subscribe(on_state)

    # Start watching the profile for changes
    config_observer = start_config_watcher(args.profile)

    try:
        vjoy.start()
        for reader in readers.values():
            reader.start()
        pulse_thread = threading.Thread(target=pulse_loop, name="PulseLoop", daemon=True)
        pulse_thread.start()
        LOG.info("flightbridge running — press Ctrl+C to stop")
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        LOG.info("shutdown requested")
    finally:
        stop_event.set()
        if pulse_thread:
            pulse_thread.join(timeout=1.0)
        for reader in readers.values():
            reader.stop()
        vjoy.stop()
        if led_controller:
            led_controller.disconnect()
        if config_observer:
            config_observer.stop()
            config_observer.join()
        vjoy.stop()


if __name__ == "__main__":
    main()

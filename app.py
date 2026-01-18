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
from devices.flight_panel import FlightPanelReader
from devices.flight_panel_leds import FlightPanelLEDControl
from devices.ch_throttle import CHThrottleReader
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

LOG = logging.getLogger("flightbridge")


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
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format=args.log_format)
    
    # Set DEBUG level for specific modules if requested
    module_map = {
        "panel": "flightbridge.panel",
        "x55": "flightbridge.x55",
        "throttle": "flightbridge.ch_throttle",
        "vjoy": "flightbridge.vjoy",
        "mapper": "flightbridge.mapper",
    }
    for module in args.debug_modules:
        logger_name = module_map.get(module, f"flightbridge.{module}")
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

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

    x55 = X55Reader()
    panel = FlightPanelReader()
    ch_throttle = CHThrottleReader()

    stop_event = threading.Event()
    state_lock = threading.Lock()
    accumulated_state = {}  # Store merged state from all devices

    def on_state(state):
        with state_lock:
            # Merge this device's state into accumulated state
            device_name = state.get("device")
            accumulated_state[device_name] = state
        # Map the full accumulated state using the current mapper atomically
        with mapper_lock:
            cmd = mapper.map_state_to_vjoy_full(accumulated_state)
        vjoy.apply(cmd)

    x55.subscribe(on_state)
    panel.subscribe(on_state)
    ch_throttle.subscribe(on_state)

    # Start watching the profile for changes
    config_observer = start_config_watcher(args.profile)

    try:
        vjoy.start()
        x55.start()
        panel.start()
        ch_throttle.start()
        LOG.info("flightbridge running — press Ctrl+C to stop")
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        LOG.info("shutdown requested")
    finally:
        x55.stop()
        panel.stop()
        ch_throttle.stop()
        vjoy.stop()
        if led_controller:
            led_controller.disconnect()
        if config_observer:
            config_observer.stop()
            config_observer.join()
        vjoy.stop()


if __name__ == "__main__":
    main()

"""Entry point for flightbridge

Starts device readers, mapping, and vJoy output loop using a chosen profile.
"""
import argparse
import logging
import signal
import threading
import time

from mapper import Mapper
from vjoy.output import VJoyOutput
from devices.x55_directinput import X55Reader
from devices.flight_panel import FlightPanelReader

LOG = logging.getLogger("flightbridge")


def main():
    parser = argparse.ArgumentParser(description="Flightbridge: X55 + FlightPanel → vJoy")
    parser.add_argument("--profile", required=True, help="YAML mapping profile")
    parser.add_argument("--vjoy-id", type=int, default=1, help="vJoy device id")
    parser.add_argument("--hz", type=int, default=60, help="vJoy update frequency")
    parser.add_argument("--log-level", default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level (default: INFO)")
    parser.add_argument("--log-format", default="%(levelname)s:%(name)s:%(message)s",
                        help="Logging format string (default: %(levelname)s:%(name)s:%(message)s)")
    parser.add_argument("--debug-modules", nargs="*", default=[],
                        help="Modules to set to DEBUG level (e.g., 'panel', 'x55', 'vjoy', 'mapper')")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format=args.log_format)
    
    # Set DEBUG level for specific modules if requested
    module_map = {
        "panel": "flightbridge.panel",
        "x55": "flightbridge.x55",
        "vjoy": "flightbridge.vjoy",
        "mapper": "flightbridge.mapper",
    }
    for module in args.debug_modules:
        logger_name = module_map.get(module, f"flightbridge.{module}")
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    mapper = Mapper.load_profile(args.profile)
    vjoy = VJoyOutput(args.vjoy_id, hz=args.hz)

    x55 = X55Reader()
    panel = FlightPanelReader()

    stop_event = threading.Event()

    def on_state(state):
        cmd = mapper.map_state_to_vjoy(state)
        vjoy.apply(cmd)

    x55.subscribe(on_state)
    panel.subscribe(on_state)

    try:
        vjoy.start()
        x55.start()
        panel.start()
        LOG.info("flightbridge running — press Ctrl+C to stop")
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        LOG.info("shutdown requested")
    finally:
        x55.stop()
        panel.stop()
        vjoy.stop()


if __name__ == "__main__":
    main()

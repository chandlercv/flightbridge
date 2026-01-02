"""CH Throttle reader using DirectInput via pygame.joystick

This module provides a `CHThrottleReader` that polls axes/buttons and emits
normalized DeviceState dictionaries to subscribers.

Supports Arduino Leonardo-based CH throttle controller with 1 throttle axis and 12 buttons.
VID: 2341 (Arduino)
PID: 8036
MI: 02 (Multiple Interface 02)
"""
import threading
import time
import logging

try:
    import pygame
except Exception:
    pygame = None

LOG = logging.getLogger("flightbridge.ch_throttle")


class CHThrottleReader:
    """Reads CH Throttle via pygame.joystick (DirectInput).

    Emits dictionaries like:
      {
        'device': 'ch_throttle',
        'axes': {0: float},  # throttle axis normalized to 0.0-1.0
        'buttons': {0: bool, 1: bool, ..., 11: bool},
        'hats': {}
      }
    """

    def __init__(self):
        self._subs = []
        self._t = None
        self._stop = threading.Event()
        self._joystick = None

    def _find_ch_throttle(self):
        if pygame is None:
            LOG.warning("pygame not available — CHThrottleReader disabled")
            return None
        pygame.init()
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            name = js.get_name() or ""
            # Try to match by name or VID/PID
            if "ch" in name.lower() or "throttle" in name.lower() or "arduino" in name.lower():
                LOG.info(f"Found joystick: {name} (index {i}, axes={js.get_numaxes()}, buttons={js.get_numbuttons()}, hats={js.get_numhats()})")
                return js
        LOG.warning("No CH Throttle joystick found via pygame")
        return None

    def subscribe(self, callback):
        self._subs.append(callback)

    def start(self):
        self._stop.clear()
        self._joystick = self._find_ch_throttle()
        self._t = threading.Thread(target=self._loop, name="CHThrottleReader", daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.0)

    def _emit(self, state):
        LOG.debug("ch_throttle raw state -> %s", state)
        for cb in self._subs:
            try:
                cb(state)
            except Exception:
                LOG.exception("subscriber callback failed")

    def _loop(self):
        if self._joystick is None:
            # try reconnect logic
            while not self._stop.is_set():
                self._joystick = self._find_ch_throttle()
                if self._joystick:
                    break
                time.sleep(1.0)
        while not self._stop.is_set():
            try:
                pygame.event.pump()
                js = self._joystick
                if js is None:
                    time.sleep(0.5)
                    continue
                # Read throttle axis (axis 0), remap from -1.0..1.0 to -1.0..1.0 (for vJoy compatibility)
                # pygame gives -1.0 at full throttle, 1.0 at zero throttle (typical for throttle axes)
                # We want: throttle down (pygame 1.0) = -1.0 (vJoy 0%), throttle up (pygame -1.0) = 1.0 (vJoy 100%)
                raw_throttle = js.get_axis(0)
                throttle = -raw_throttle  # Invert so throttle up = 1.0
                axes = {0: throttle}
                
                # Read buttons 0-11
                buttons = {i: bool(js.get_button(i)) for i in range(min(12, js.get_numbuttons()))}
                
                state = {"device": "ch_throttle", "axes": axes, "buttons": buttons, "hats": {}}
                self._emit(state)
                time.sleep(1.0 / 120.0)
            except Exception:
                LOG.exception("error reading CH Throttle; will attempt reconnect")
                self._joystick = None
                time.sleep(1.0)

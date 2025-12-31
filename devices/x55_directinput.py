"""X-55 reader using DirectInput via pygame.joystick

This module provides a simple `X55Reader` that polls axes/buttons/hats and emits
normalized DeviceState dictionaries to subscribers.
"""
import threading
import time
import logging

try:
    import pygame
except Exception:
    pygame = None

LOG = logging.getLogger("flightbridge.x55")


class X55Reader:
    """Reads a Saitek X-55 via pygame.joystick (DirectInput).

    Emits dictionaries like:
      {
        'device': 'x55',
        'axes': {0: float, 1: float, ...},
        'buttons': {0: bool, 1: bool, ...},
        'hats': {0: (x,y), ...}
      }
    """

    def __init__(self):
        self._subs = []
        self._t = None
        self._stop = threading.Event()
        self._joystick = None

    def _find_x55(self):
        if pygame is None:
            LOG.warning("pygame not available — X55Reader disabled")
            return None
        pygame.init()
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            name = js.get_name() or ""
            if "x-55" in name.lower() or "saitek" in name.lower():
                LOG.info(f"Found joystick: {name} (index {i}, axes={js.get_numaxes()}, buttons={js.get_numbuttons()}, hats={js.get_numhats()})")
                return js
        LOG.warning("No X-55 joystick found via pygame")
        return None

    def subscribe(self, callback):
        self._subs.append(callback)

    def start(self):
        self._stop.clear()
        self._joystick = self._find_x55()
        self._t = threading.Thread(target=self._loop, name="X55Reader", daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.0)

    def _emit(self, state):
        LOG.debug("x55 raw state -> %s", state)
        for cb in self._subs:
            try:
                cb(state)
            except Exception:
                LOG.exception("subscriber callback failed")

    def _loop(self):
        if self._joystick is None:
            # try reconnect logic
            while not self._stop.is_set():
                self._joystick = self._find_x55()
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
                axes = {i: js.get_axis(i) for i in range(js.get_numaxes())}
                buttons = {i: bool(js.get_button(i)) for i in range(js.get_numbuttons())}
                hats = {i: js.get_hat(i) for i in range(js.get_numhats())}
                state = {"device": "x55", "axes": axes, "buttons": buttons, "hats": hats}
                self._emit(state)
                time.sleep(1.0 / 120.0)
            except Exception:
                LOG.exception("error reading X55; will attempt reconnect")
                self._joystick = None
                time.sleep(1.0)

"""Flight panel reader using USB HID

Reads Logitech Flight Switch Panel (PID 0xd67e) and emits button/switch states.
"""
import threading
import logging
import time

LOG = logging.getLogger("flightbridge.panel")

# Saitek Pro Flight Switch Panel USB IDs
LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67

# Attempt to import hid library for real hardware support
try:
    import hid
    HAS_HID = True
except ImportError:
    HAS_HID = False
    LOG.warning("hidapi not installed — FlightPanelReader will run in stub mode")


class FlightPanelReader:
    def __init__(self):
        self._subs = []
        self._t = None
        self._stop = threading.Event()
        self._device = None
        self._endpoint = None
        self._last_state = None

    def subscribe(self, cb):
        self._subs.append(cb)

    def start(self):
        self._stop.clear()
        if HAS_HID:
            try:
                self._device = hid.device()
                self._device.open(LOGITECH_VID, FLIGHT_PANEL_PID)
                LOG.info("Flight Panel found, interface claimed")
            except Exception as e:
                LOG.warning("Flight Panel not found via HID (VID:%04x, PID:%04x): %s", LOGITECH_VID, FLIGHT_PANEL_PID, e)
                self._device = None
        
        self._t = threading.Thread(target=self._loop, name="FlightPanelReader", daemon=True)
        self._t.start()
        if self._device is None and HAS_HID:
            LOG.info("FlightPanelReader started (stub — hardware not found)")
        elif self._device is None:
            LOG.info("FlightPanelReader started (stub — hidapi not available)")
        else:
            LOG.info("FlightPanelReader started (hardware mode)")

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=0.5)
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass

    def _loop(self):
        while not self._stop.is_set():
            if self._device:
                try:
                    # Read up to 64 bytes with 100ms timeout
                    data = self._device.read(64, timeout_ms=100)
                    if data:
                        self._parse_and_emit(data)
                except Exception as e:
                    LOG.exception("Error reading from Flight Panel: %s", e)
                    self._device = None
            else:
                # Stub mode: sleep to avoid busy loop
                self._stop.wait(0.1)

    def _parse_and_emit(self, data):
        """Parse raw USB HID report from Flight Switch Panel.
        
        The Flight Switch Panel typically sends an 8-byte HID report where each byte
        represents switch/button states. Map the bits to logical switch indices.
        """
        if not data or len(data) < 3:
            return
        
        # Simple parsing: treat bytes as switch state bits
        # Flight panel has about 12 switches/buttons, map them to indices
        state = {
            "device": "flightpanel",
            "buttons": {},
            "axes": {},
            "hats": {},
        }
        
        # Decode HID report (varies by panel model; this is a typical layout)
        # Byte 0 might be report ID, bytes 1-8 contain switch bits
        for byte_idx, byte_val in enumerate(data[1:] if data[0] == 0 else data):  # skip report ID if present
            for bit_idx in range(8):
                if byte_idx * 8 + bit_idx < 20:  # reasonable max switches
                    switch_idx = byte_idx * 8 + bit_idx
                    state["buttons"][switch_idx] = bool((byte_val >> bit_idx) & 1)
        
        # Only emit if state changed
        if state != self._last_state:
            self._last_state = state
            self._emit(state)

    def _emit(self, state):
        LOG.debug("FlightPanel: emit %r", state)
        for cb in self._subs:
            cb(state)

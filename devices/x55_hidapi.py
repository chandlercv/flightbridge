"""X-55 reader using hidapi (direct HID, bypasses DirectInput & HIDHide)

This module provides a `X55Reader` that accesses the X-55 via the Windows HID API
directly, bypassing DirectInput entirely. This allows it to work with HIDHide even
when the device is hidden from games.

Emits dictionaries like:
  {
    'device': 'x55',
    'axes': {0: float, 1: float, ...},
    'buttons': {0: bool, 1: bool, ...},
    'hats': {0: (x,y), ...}
  }
"""
import threading
import time
import logging
import struct

try:
    import hid
except Exception:
    hid = None

LOG = logging.getLogger("flightbridge.x55")

# Saitek X-55 VID/PID
# These are the typical values for the X-55; adjust if needed
X55_VENDOR_ID = 0x0738  # Saitek
X55_PRODUCT_ID = 0x2215  # X-55 Rhino


class X55Reader:
    """Reads a Saitek X-55 via hidapi (direct HID access).

    Bypasses DirectInput and SDL2, so it works with HIDHide.
    """

    def __init__(self, vendor_id=X55_VENDOR_ID, product_id=X55_PRODUCT_ID):
        self._subs = []
        self._t = None
        self._stop = threading.Event()
        self._device = None
        self._vendor_id = vendor_id
        self._product_id = product_id
        self._last_state = None
        self._deadzone = 0.05  # 5% deadzone for change detection
        self._axis_smoothing = {}  # Exponential moving average for axes

    def _find_x55(self):
        """Find and open the X-55 device via hidapi."""
        if hid is None:
            LOG.warning("hidapi not available — X55Reader disabled")
            return None
        
        try:
            device = hid.device()
            device.open(self._vendor_id, self._product_id)
            info = device.get_manufacturer_string() or ""
            prod = device.get_product_string() or ""
            LOG.info(f"Found X-55 via hidapi: {info} {prod}")
            return device
        except OSError as e:
            LOG.warning(f"Failed to open X-55 device: {e}")
            return None

    def subscribe(self, callback):
        """Register a callback to receive state updates."""
        self._subs.append(callback)

    def start(self):
        """Start the reader thread."""
        self._stop.clear()
        self._device = self._find_x55()
        self._t = threading.Thread(target=self._loop, name="X55Reader", daemon=True)
        self._t.start()

    def stop(self):
        """Stop the reader thread."""
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.0)
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass

    def _emit(self, state):
        """Emit state to all subscribers."""
        LOG.info("x55 raw state -> %s", state)
        for cb in self._subs:
            try:
                cb(state)
            except Exception:
                LOG.exception("subscriber callback failed")

    def _parse_x55_report(self, data):
        """
        Parse raw HID report from X-55.
        
        X-55 stick reports are 9 bytes with:
        - Byte 0: Stick X (8-bit)
        - Byte 1: Fixed at 0x80
        - Byte 2: Stick Y (8-bit)
        - Byte 3: Fixed at 0x7F
        - Byte 4: Z-axis / some throttle
        - Byte 5-6: More throttle/axis data
        - Byte 7: Buttons/hat (bitfield)
        - Byte 8: More button/mode data
        """
        if not data or len(data) < 9:
            LOG.debug("Skipping short/empty report: %s", data)
            return None
        
        # Log every 60th report to avoid spam but still see what's happening
        if not hasattr(self, '_report_count'):
            self._report_count = 0
        self._report_count += 1
        
        if self._report_count % 60 == 0:
            LOG.info("Raw X55 report (%d bytes): %s", len(data), " ".join(f"{b:02X}" for b in data))
            LOG.info("  Bytes 7-8 (buttons): 0x%02X 0x%02X (bin: %s %s)", data[7], data[8], 
                    bin(data[7])[2:].zfill(8), bin(data[8])[2:].zfill(8))
        
        try:
            axes = {}
            buttons = {}
            hats = {}
            
            # Parse X-55 stick (9-byte) report:
            # Byte 0: Stick X (0-255, centered ~128)
            # Byte 1: Usually 0x80 (separator/padding)
            # Byte 2: Stick Y (0-255, centered ~128)
            # Byte 3: Usually 0x7F (separator/padding)
            # Byte 4: Z-axis or throttle (0-255)
            # Byte 5: Another throttle/slider (0-255, usually 0xFF when neutral)
            # Byte 6: Another throttle/slider (0-255, usually 0x00 when neutral)
            # Byte 7: Buttons/mode byte (bitfield)
            # Byte 8: More buttons or mode indicator
            
            # Convert 8-bit values (0-255) to normalized axes (-1.0 to 1.0)
            # Centered is typically 128, so: (val - 128) / 128
            axes[0] = (data[0] - 128) / 128.0  # Stick X
            axes[1] = (data[2] - 128) / 128.0  # Stick Y
            axes[2] = (data[4] - 128) / 128.0  # Z-axis (twist/rotation)
            axes[3] = (data[5] - 128) / 128.0  # Throttle L or slider
            axes[4] = (data[6] - 128) / 128.0  # Throttle R or slider
            
            # Clamp, smooth, and apply deadzone to [-1.0, 1.0]
            for i in axes:
                axes[i] = max(-1.0, min(1.0, axes[i]))
                axes[i] = self._smooth_axis(i, axes[i])  # Smooth first
                axes[i] = self._apply_deadzone(axes[i], self._deadzone)  # Then deadzone
            
            # Parse buttons from bytes 6-7 (bitfield, typically 16 buttons)
            # Byte 6 and 7 contain button state as bitfields
            button_bytes = [data[6], data[7]]
            for i, byte in enumerate(button_bytes):
                for bit in range(8):
                    button_idx = i * 8 + bit
                    buttons[button_idx] = bool(byte & (1 << bit))
            
            # Hat/POV (usually in byte 7 upper bits or byte 8)
            # For now, assume centered if no specific POV data
            hats[0] = (0, 0)
            
            return {
                "device": "x55",
                "axes": axes,
                "buttons": buttons,
                "hats": hats,
            }
        except Exception as e:
            LOG.exception(f"Error parsing X-55 report: {e}")
            return None

    def _apply_deadzone(self, value, deadzone=0.05):
        """Apply deadzone to analog input to reduce jitter."""
        if abs(value) < deadzone:
            return 0.0
        # Scale the value so it goes from deadzone to 1.0
        if value > 0:
            return (value - deadzone) / (1.0 - deadzone)
        else:
            return (value + deadzone) / (1.0 - deadzone)
    
    def _smooth_axis(self, axis_id, value, alpha=0.3):
        """Apply exponential smoothing to axis value.
        Lower alpha = more smoothing, higher alpha = more responsive."""
        if axis_id not in self._axis_smoothing:
            self._axis_smoothing[axis_id] = value
            return value
        
        smoothed = alpha * value + (1 - alpha) * self._axis_smoothing[axis_id]
        self._axis_smoothing[axis_id] = smoothed
        return smoothed

    def _states_equal(self, state1, state2):
        """Check if two states are equal (within deadzone tolerance for axes)."""
        if state1 is None or state2 is None:
            return False
        
        # Check buttons
        if state1.get("buttons") != state2.get("buttons"):
            return False
        
        # Check hats
        if state1.get("hats") != state2.get("hats"):
            return False
        
        # Check axes with tolerance (each axis must differ by more than deadzone)
        axes1 = state1.get("axes", {})
        axes2 = state2.get("axes", {})
        
        for axis_id in axes1:
            val1 = axes1.get(axis_id, 0)
            val2 = axes2.get(axis_id, 0)
            # Consider equal if difference is less than deadzone
            if abs(val1 - val2) > self._deadzone:
                return False
        
        return True
        # Standard POV encoding:
        # 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 0xFF=centered
        hat_map = {
            0xFF: (0, 0),
            0: (0, 1),    # North
            1: (1, 1),    # NE
            2: (1, 0),    # East
            3: (1, -1),   # SE
            4: (0, -1),   # South
            5: (-1, -1),  # SW
            6: (-1, 0),   # West
            7: (-1, 1),   # NW
        }
        return hat_map.get(hat_val, (0, 0))

    def _loop(self):
        """Main read loop."""
        if self._device is None:
            # Try to reconnect
            while not self._stop.is_set():
                self._device = self._find_x55()
                if self._device:
                    break
                time.sleep(1.0)
        
        while not self._stop.is_set():
            try:
                if self._device is None:
                    time.sleep(0.5)
                    continue
                
                # Read from HID device (non-blocking, 100ms timeout)
                data = self._device.read(64, timeout_ms=100)
                
                if data:
                    state = self._parse_x55_report(data)
                    if state:
                        # Only emit if state actually changed (not just analog noise)
                        if not self._states_equal(state, self._last_state):
                            self._emit(state)
                            self._last_state = state
                
                time.sleep(1.0 / 120.0)  # ~120 Hz polling
            except Exception as e:
                LOG.exception(f"Error reading X55: {e}")
                self._device = None
                time.sleep(1.0)

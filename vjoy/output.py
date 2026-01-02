"""vJoy output wrapper using direct ctypes calls to vJoy DLL

This provides `VJoyOutput` that accepts VJoyCommand objects and sends them to vJoy
via direct DLL calls. This approach is more reliable than pyvjoy which is outdated.
"""
import ctypes
import threading
import logging
from queue import Queue, Empty

from core.state import VJoyCommand

LOG = logging.getLogger("flightbridge.vjoy")

# Load vJoy DLL
try:
    vjoy_dll = ctypes.CDLL(r"C:\Program Files\vJoy\x64\vJoyInterface.dll")
    VJOY_AVAILABLE = True
    LOG.info("vJoy DLL loaded successfully")
except OSError as e:
    vjoy_dll = None
    VJOY_AVAILABLE = False
    LOG.error("Failed to load vJoy DLL: %s — vJoy may not be installed or path may be wrong", e)


class JOYSTICK_POSITION(ctypes.Structure):
    """vJoy joystick position structure matching vJoy SDK"""
    _fields_ = [
        ("bDevice", ctypes.c_ubyte),
        ("wThrottle", ctypes.c_ulong),
        ("wRudder", ctypes.c_ulong),
        ("wAileron", ctypes.c_ulong),
        ("wAxisX", ctypes.c_long),
        ("wAxisY", ctypes.c_long),
        ("wAxisZ", ctypes.c_long),
        ("wAxisXRot", ctypes.c_long),
        ("wAxisYRot", ctypes.c_long),
        ("wAxisZRot", ctypes.c_long),
        ("wSlider", ctypes.c_long),
        ("wDial", ctypes.c_long),
        ("wWheel", ctypes.c_long),
        ("wAxisVX", ctypes.c_long),
        ("wAxisVY", ctypes.c_long),
        ("wAxisVZ", ctypes.c_long),
        ("wAxisVBRX", ctypes.c_long),
        ("wAxisVBRY", ctypes.c_long),
        ("wAxisVBRZ", ctypes.c_long),
        ("lButtons", ctypes.c_ulong),
        ("bHats", ctypes.c_ulong),
        ("bHatsEx1", ctypes.c_ubyte),
        ("bHatsEx2", ctypes.c_ubyte),
        ("bHatsEx3", ctypes.c_ubyte),
    ]


# Map axis names to JOYSTICK_POSITION field names
AXIS_MAP = {
    "AXIS_X": "wAxisX",
    "AXIS_Y": "wAxisY",
    "AXIS_Z": "wAxisZ",
    "AXIS_RX": "wAxisXRot",
    "AXIS_RY": "wAxisYRot",
    "AXIS_RZ": "wAxisZRot",
    "AXIS_RUDDER": "wRudder",
    "AXIS_THROTTLE": "wThrottle",
    "AXIS_AILERON": "wAileron",
    "AXIS_SLIDER": "wSlider",
    "AXIS_DIAL": "wDial",
    "AXIS_WHEEL": "wWheel",
}

if VJOY_AVAILABLE:
    vjoy_dll.AcquireVJD.argtypes = [ctypes.c_uint]
    vjoy_dll.AcquireVJD.restype = ctypes.c_bool
    vjoy_dll.RelinquishVJD.argtypes = [ctypes.c_uint]
    vjoy_dll.RelinquishVJD.restype = ctypes.c_bool
    vjoy_dll.UpdateVJD.argtypes = [ctypes.c_uint, ctypes.POINTER(JOYSTICK_POSITION)]
    vjoy_dll.UpdateVJD.restype = ctypes.c_bool
    vjoy_dll.GetVJDStatus.argtypes = [ctypes.c_uint]
    vjoy_dll.GetVJDStatus.restype = ctypes.c_uint


class VJoyOutput:
    def __init__(self, device_id: int = 1, hz: int = 60, device_ids: list = None):
        """Initialize vJoy output
        
        Args:
            device_id: Primary vJoy device ID (for backwards compatibility)
            hz: Update frequency
            device_ids: List of vJoy device IDs to use (e.g., [1, 2] for 64 buttons)
                       If None, uses only device_id for 32 buttons
        """
        if device_ids is None:
            device_ids = [device_id]
        self.device_ids = device_ids
        self.hz = hz
        self._q = Queue(maxsize=4)
        self._t = None
        self._stop = threading.Event()
        self._positions = {did: JOYSTICK_POSITION() for did in device_ids}
        for did in device_ids:
            self._positions[did].bDevice = did
        self._acquired = {did: False for did in device_ids}

        if VJOY_AVAILABLE:
            for did in device_ids:
                try:
                    if vjoy_dll.AcquireVJD(did):
                        self._acquired[did] = True
                        LOG.info("vJoy device %d acquired", did)
                    else:
                        LOG.warning("Failed to acquire vJoy device %d — make sure vJoy Monitor is running", did)
                        # Check status to provide more info
                        status = vjoy_dll.GetVJDStatus(did)
                        status_names = {0: "FREE", 1: "TAKEN", 2: "BUSY", 3: "MISS", 4: "UNKNOWN"}
                        status_name = status_names.get(status, f"UNKNOWN({status})")
                        LOG.warning("Device %d status: %s (close vJoy config tools if BUSY)", did, status_name)
                except Exception:
                    LOG.exception("Error acquiring vJoy device %d", did)
        else:
            LOG.warning("vJoy not available — running in dry-run mode")

    def apply(self, cmd: VJoyCommand):
        # keep only the latest command
        try:
            self._q.put_nowait(cmd)
        except Exception:
            try:
                _ = self._q.get_nowait()
            except Exception:
                pass
            finally:
                try:
                    self._q.put_nowait(cmd)
                except Exception:
                    LOG.exception("failed to enqueue vjoy command")

    def start(self):
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, name="VJoyOutput", daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.0)
        if VJOY_AVAILABLE:
            for did in self.device_ids:
                if self._acquired.get(did):
                    try:
                        vjoy_dll.RelinquishVJD(did)
                        LOG.info("vJoy device %d released", did)
                    except Exception:
                        LOG.exception("Error releasing vJoy device %d", did)

    def _to_vjoy_axis(self, val: float) -> int:
        # map -1..1 to 0..0x8000
        iv = int((val + 1.0) / 2.0 * 0x8000)
        iv = max(0, min(0x8000, iv))
        return iv

    def _apply_to_device(self, cmd: VJoyCommand):
        if not any(self._acquired.values()):
            LOG.debug("vjoy dry-run: axes=%s buttons=%s povs=%s", cmd.axes, cmd.buttons, cmd.povs)
            return

        try:
            # Apply axes to device 1 only (all axes go to primary device)
            device_id = self.device_ids[0]
            pos = self._positions[device_id]
            
            # Set axes
            for name, v in cmd.axes.items():
                field_name = AXIS_MAP.get(name)
                if field_name:
                    iv = self._to_vjoy_axis(v)
                    setattr(pos, field_name, iv)
                    LOG.debug("set axis %s -> %d", name, iv)
                else:
                    LOG.debug("unknown vjoy axis %s", name)

            # Set POVs (device 1 only)
            if cmd.povs:
                for pid, deg in cmd.povs.items():
                    if pid == 0:
                        if deg == -1:
                            pos.bHats = 0xFFFF  # centered
                        else:
                            # Convert 0-360 degrees to DirectInput format (hundredths of degrees, 0-35999)
                            # Normalize to 0-360 range
                            deg_normalized = deg % 360
                            # Convert to hundredths of degrees
                            hat_val = int(deg_normalized * 100)
                            pos.bHats = hat_val
                        LOG.debug("set pov %d -> 0x%x (degrees: %s)", pid, pos.bHats, deg)

            # Distribute buttons across devices: 1-32 → device 1, 33-64 → device 2, etc.
            device_buttons = {did: 0 for did in self.device_ids}
            for bid, state in cmd.buttons.items():
                if state:
                    # Calculate which device this button belongs to
                    device_index = (bid - 1) // 32
                    if device_index < len(self.device_ids):
                        device_id = self.device_ids[device_index]
                        # Calculate button position within that device (0-31)
                        button_bit = (bid - 1) % 32
                        device_buttons[device_id] |= (1 << button_bit)

            # Apply button states to each device
            for did in self.device_ids:
                self._positions[did].lButtons = device_buttons[did]
                if device_buttons[did]:
                    LOG.debug("set device %d buttons -> 0x%x", did, device_buttons[did])

            # Send updates to all acquired devices
            for did in self.device_ids:
                if self._acquired.get(did):
                    if not vjoy_dll.UpdateVJD(did, ctypes.byref(self._positions[did])):
                        LOG.warning("vJoy UpdateVJD failed for device %d", did)

        except Exception:
            LOG.exception("failed to write to vJoy device")

    def _loop(self):
        period = 1.0 / float(self.hz)
        while not self._stop.is_set():
            try:
                cmd = self._q.get(timeout=period)
                self._apply_to_device(cmd)
            except Empty:
                pass
            except Exception:
                LOG.exception("error in vjoy output loop")


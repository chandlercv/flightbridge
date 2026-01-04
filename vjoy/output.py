"""vJoy output wrapper using direct ctypes calls to vJoy DLL

This provides `VJoyOutput` that accepts VJoyCommand objects and sends them to vJoy
via direct DLL calls. This approach is more reliable than pyvjoy which is outdated.
Keyboard support uses pynput for cross-platform key sending.
"""
import ctypes
import threading
import logging
from queue import Queue, Empty

from core.state import VJoyCommand

try:
    from pynput.keyboard import Controller, Key
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

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
        
        # Initialize keyboard controller and track key states
        if KEYBOARD_AVAILABLE:
            self._keyboard = Controller()
            self._key_states = {}  # Track which keys are currently pressed
            LOG.info("Keyboard support enabled (pynput)")
        else:
            self._keyboard = None
            self._key_states = {}
            LOG.warning("pynput not installed — keyboard support disabled. Install with: pip install pynput")
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
        # Release all keyboard keys before shutting down
        self._release_all_keys()
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

    def _get_pynput_key(self, key_name: str):
        """Convert key name string to pynput Key object
        
        Supports:
        - Named keys: 'space', 'enter', 'shift', 'ctrl', 'alt', 'cmd', 'win', 'tab', 'backspace', etc.
        - Single characters: 'a', '1', '.', etc.
        """
        if not KEYBOARD_AVAILABLE or not self._keyboard:
            return None
        
        key_name_lower = key_name.lower().strip()
        
        # Map common key names to pynput.Key
        key_map = {
            'space': Key.space,
            'enter': Key.enter,
            'return': Key.enter,
            'tab': Key.tab,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'insert': Key.insert,
            'home': Key.home,
            'end': Key.end,
            'pageup': Key.page_up,
            'page_up': Key.page_up,
            'pagedown': Key.page_down,
            'page_down': Key.page_down,
            'up': Key.up,
            'down': Key.down,
            'left': Key.left,
            'right': Key.right,
            'escape': Key.esc,
            'esc': Key.esc,
            'shift': Key.shift,
            'shift_l': Key.shift,
            'shift_r': Key.shift_r,
            'ctrl': Key.ctrl_l,
            'ctrl_l': Key.ctrl_l,
            'ctrl_r': Key.ctrl_r,
            'control': Key.ctrl_l,
            'alt': Key.alt_l,
            'alt_l': Key.alt_l,
            'alt_r': Key.alt_r,
            'cmd': Key.cmd,
            'cmd_l': Key.cmd,
            'cmd_r': Key.cmd_r,
            'win': Key.cmd,
            'windows': Key.cmd,
            'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
            'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
            'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
        }
        
        if key_name_lower in key_map:
            return key_map[key_name_lower]
        
        # For single character keys, try to use the character directly
        if len(key_name) == 1:
            return key_name
        
        LOG.warning("Unknown key name: %s", key_name)
        return None

    def _send_keyboard_keys(self, cmd: VJoyCommand):
        """Send keyboard key presses/releases based on command"""
        if not self._keyboard or not KEYBOARD_AVAILABLE:
            return
        
        try:
            # Ensure we release keys that are currently pressed but not present in this command
            for key_name, is_pressed in list(self._key_states.items()):
                if is_pressed and key_name not in cmd.keys:
                    cmd.keys[key_name] = False

            # Process each key in the command
            for key_name, should_press in cmd.keys.items():
                pynput_key = self._get_pynput_key(key_name)
                if pynput_key is None:
                    continue
                
                current_state = self._key_states.get(key_name, False)
                
                # State change detected
                if should_press and not current_state:
                    # Key should be pressed
                    self._keyboard.press(pynput_key)
                    self._key_states[key_name] = True
                    LOG.debug("keyboard: pressed %s", key_name)
                elif not should_press and current_state:
                    # Key should be released
                    self._keyboard.release(pynput_key)
                    self._key_states[key_name] = False
                    LOG.debug("keyboard: released %s", key_name)
        except Exception:
            LOG.exception("failed to send keyboard command")
    
    def _release_all_keys(self):
        """Release all currently pressed keys on shutdown"""
        if not self._keyboard or not KEYBOARD_AVAILABLE:
            return
        
        try:
            for key_name, is_pressed in list(self._key_states.items()):
                if is_pressed:
                    pynput_key = self._get_pynput_key(key_name)
                    if pynput_key:
                        self._keyboard.release(pynput_key)
                        LOG.debug("keyboard: released %s (shutdown)", key_name)
        except Exception:
            LOG.exception("failed to release keyboard keys on shutdown")

    def _apply_to_device(self, cmd: VJoyCommand):
        # Send keyboard commands first
        self._send_keyboard_keys(cmd)
        
        if not any(self._acquired.values()):
            LOG.debug("vjoy dry-run: axes=%s buttons=%s povs=%s keys=%s", cmd.axes, cmd.buttons, cmd.povs, cmd.keys)
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


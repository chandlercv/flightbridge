"""Direct vJoy control via ctypes - calls vJoy DLL directly"""
import ctypes
import os

# Load vJoy DLL from vJoy installation
vjoy_dll_path = r"C:\Program Files\vJoy\x64\vJoyInterface.dll"
vjoy_dll = ctypes.CDLL(vjoy_dll_path)
print(f"Loaded vJoy DLL from: {vjoy_dll_path}\n")

# vJoy structure and constants
VJD_STAT_OWN = 1

class JOYSTICK_POSITION(ctypes.Structure):
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
        ("bHats", ctypes.c_ubyte),
        ("bHatsEx1", ctypes.c_ubyte),
        ("bHatsEx2", ctypes.c_ubyte),
        ("bHatsEx3", ctypes.c_ubyte),
    ]

# Set up function signatures
vjoy_dll.AcquireVJD.argtypes = [ctypes.c_uint]
vjoy_dll.AcquireVJD.restype = ctypes.c_bool

vjoy_dll.RelinquishVJD.argtypes = [ctypes.c_uint]
vjoy_dll.RelinquishVJD.restype = ctypes.c_bool

vjoy_dll.UpdateVJD.argtypes = [ctypes.c_uint, ctypes.POINTER(JOYSTICK_POSITION)]
vjoy_dll.UpdateVJD.restype = ctypes.c_bool

vjoy_dll.GetVJDStatus.argtypes = [ctypes.c_uint]
vjoy_dll.GetVJDStatus.restype = ctypes.c_uint

print("Testing direct vJoy DLL calls...\n")

device_id = 1

# Check device status
status = vjoy_dll.GetVJDStatus(device_id)
print(f"Device {device_id} status: {status}")

# Acquire device
if vjoy_dll.AcquireVJD(device_id):
    print(f"Device {device_id} acquired successfully")
    
    # Create and update position
    pos = JOYSTICK_POSITION()
    pos.bDevice = device_id
    pos.wAxisX = 0
    pos.wAxisY = 0
    
    print("\nSetting axes to min/max values...")
    for i in range(5):
        pos.wAxisX = 0
        pos.wAxisY = 0
        vjoy_dll.UpdateVJD(device_id, ctypes.byref(pos))
        print(f"{i}: X=0, Y=0")
        
        import time
        time.sleep(0.5)
        
        pos.wAxisX = 0x8000
        pos.wAxisY = 0x8000
        vjoy_dll.UpdateVJD(device_id, ctypes.byref(pos))
        print(f"{i}: X=32768, Y=32768")
        
        time.sleep(0.5)
    
    vjoy_dll.RelinquishVJD(device_id)
    print(f"\nDevice {device_id} released")
else:
    print(f"Failed to acquire device {device_id}")

print("\nDid vJoy Monitor show X/Y axis movement?")

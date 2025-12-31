import time
import pyvjoy

d = pyvjoy.VJoyDevice(1)
print("Opened vJoy device 1")

# Try to acquire
try:
    d.acquire()
    print("Device acquired")
except:
    print("Could not acquire (continuing anyway)")

print("\nWriting min/max axis values in a loop...")
print("Watch vJoy Monitor X axis - it should swing left-right")

for i in range(10):
    print(f"\n{i}: Setting X to MIN (0)")
    d.set_axis(pyvjoy.HID_USAGE_X, 0)
    d.update()
    time.sleep(0.5)
    
    print(f"{i}: Setting X to MAX (0x8000)")
    d.set_axis(pyvjoy.HID_USAGE_X, 0x8000)
    d.update()
    time.sleep(0.5)

print("\nDone. Did vJoy Monitor show the X axis moving?")

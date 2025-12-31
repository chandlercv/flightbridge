import pyvjoy
import time

print("Testing direct data manipulation...\n")

d = pyvjoy.VJoyDevice(1)

# Inspect the data object structure
print("VJoyDevice.data type:", type(d.data))
print("VJoyDevice.data attributes:", dir(d.data))

print("\n--- Test: Direct axis field assignment ---")
try:
    # Try accessing axis fields directly
    if hasattr(d.data, 'bAxisX'):
        print("Found bAxisX field")
        d.data.bAxisX = 0
        d.update()
        print("Set bAxisX to 0")
        time.sleep(0.3)
        d.data.bAxisX = 0x8000
        d.update()
        print("Set bAxisX to 0x8000")
    elif hasattr(d.data, 'Axis'):
        print("Found Axis field (array?)")
        print("Trying Axis[0]...")
        d.data.Axis[0] = 0
        d.update()
        time.sleep(0.3)
        d.data.Axis[0] = 0x8000
        d.update()
        print("Set Axis[0]")
except Exception as e:
    print(f"Direct field access failed: {e}")

print("\nDone. Did the Monitor move?")

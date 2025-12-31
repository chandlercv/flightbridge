import pyvjoy
import time

print("Testing different pyvjoy axis constants and methods...\n")

d = pyvjoy.VJoyDevice(1)

# List all pyvjoy constants that might be axis identifiers
print("Available pyvjoy constants:")
constants = {name: getattr(pyvjoy, name) for name in dir(pyvjoy) if name.isupper() and not name.startswith('_')}
for name in sorted([n for n in constants.keys() if 'AXIS' in n or 'HID' in n or 'JOY' in n or 'X' in n or 'Y' in n]):
    print(f"  {name}: {constants[name]}")

print("\n--- Test 1: HID_USAGE constants (current approach) ---")
try:
    d.set_axis(pyvjoy.HID_USAGE_X, 0)
    d.update()
    print("HID_USAGE_X set to 0: SUCCESS")
    time.sleep(0.3)
    d.set_axis(pyvjoy.HID_USAGE_X, 0x8000)
    d.update()
    print("HID_USAGE_X set to 0x8000: SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")

print("\n--- Test 2: Try numeric axis IDs 0, 1, 2... ---")
for axis_id in range(8):
    try:
        d.set_axis(axis_id, 0x4000)
        d.update()
        print(f"Axis ID {axis_id}: SUCCESS (mid-range value)")
        time.sleep(0.5)
    except Exception as e:
        print(f"Axis ID {axis_id}: FAILED - {e}")

print("\nDone. Did the Monitor move on any of these tests?")

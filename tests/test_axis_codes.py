import pyvjoy

d = pyvjoy.VJoyDevice(1)

# Try different axis codes and see what pyvjoy accepts
test_codes = [
    ('HID_USAGE_X', pyvjoy.HID_USAGE_X),
    ('HID_USAGE_Y', pyvjoy.HID_USAGE_Y),
]

# Also try predefined constants if they exist
for attr in dir(pyvjoy):
    if 'X' in attr and ('AXIS' in attr or 'JOY' in attr):
        val = getattr(pyvjoy, attr)
        if isinstance(val, int):
            test_codes.append((attr, val))
            break

print("Testing axis codes:")
for name, code in test_codes[:2]:
    try:
        d.set_axis(code, 0x4000)
        print(f"  {name} ({code}): SUCCESS")
    except Exception as e:
        print(f"  {name} ({code}): ERROR - {e}")

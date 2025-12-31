import pyvjoy

print("Checking pyvjoy device info:\n")

d = pyvjoy.VJoyDevice(1)

print(f"Device ID: {d.rID if hasattr(d, 'rID') else 'N/A'}")
print(f"Device data.bDevice: {d.data.bDevice if hasattr(d.data, 'bDevice') else 'N/A'}")

# Check if device is actually acquired/enabled
print(f"\nDevice status attributes:")
for attr in ['rID', 'bDevice']:
    if hasattr(d, attr):
        print(f"  {attr}: {getattr(d, attr)}")
    if hasattr(d.data, attr):
        print(f"  data.{attr}: {getattr(d.data, attr)}")

# Try other fields
print(f"\nOther potential device info:")
print(f"  data.lButtons: {d.data.lButtons}")
print(f"  data.wAxisX initial: {d.data.wAxisX}")
print(f"  data.wAxisY initial: {d.data.wAxisY}")

# Try a simple write and check if data changed
print(f"\nSetting wAxisX to 12345 and checking if it sticks:")
d.data.wAxisX = 12345
print(f"  After assignment: wAxisX = {d.data.wAxisX}")
d.update()
print(f"  After update(): wAxisX = {d.data.wAxisX}")

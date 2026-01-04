import hid
import time

LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67

devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
if not devices:
    print('Device not found')
    exit(1)

device = hid.device()
device.open_path(devices[0]['path'])

# Read current
current = device.get_feature_report(0, 64)
print(f'Current state: {" ".join(f"{b:02x}" for b in current)}')
print(f'Byte 1 (landing gear LED): 0x{current[1]:02x} = {bin(current[1])}')

# Turn OFF landing gear LED (clear bit 7 of byte 1)
modified = bytearray(current)
modified[1] = modified[1] & 0x7F  # Clear bit 7
print(f'Modified (LED OFF): {" ".join(f"{b:02x}" for b in modified)}')

result = device.send_feature_report(modified)
print(f'Send result: {result}')

# Read back
time.sleep(0.5)
new_state = device.get_feature_report(0, 64)
print(f'New state:     {" ".join(f"{b:02x}" for b in new_state)}')
print(f'LED changed: {new_state[1] != current[1]}')

# Now turn it back ON
print('\nTurning LED back ON...')
modified[1] = modified[1] | 0x80  # Set bit 7
print(f'Modified (LED ON): {" ".join(f"{b:02x}" for b in modified)}')

result = device.send_feature_report(modified)
print(f'Send result: {result}')

time.sleep(0.5)
new_state = device.get_feature_report(0, 64)
print(f'New state:     {" ".join(f"{b:02x}" for b in new_state)}')

device.close()

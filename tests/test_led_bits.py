import hid

LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67

devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
device = hid.device()
device.open_path(devices[0]['path'])

print("Testing different report IDs and bytes...\n")

# Current state has byte 1 = 0x3c
current = device.get_feature_report(0, 64)
print(f'Report ID 0: {" ".join(f"{b:02x}" for b in current[:4])}')
print(f'  Byte 0: {current[0]:08b} (report ID)')
print(f'  Byte 1: {current[1]:08b} = 0x{current[1]:02x}')
print(f'  Byte 2: {current[2]:08b} = 0x{current[2]:02x}')
print(f'  Byte 3: {current[3]:08b} = 0x{current[3]:02x}')

# Try toggling each bit of byte 1 individually
print("\nToggling byte 1 bits individually:")
for bit in range(8):
    test = bytearray(current)
    test[1] = test[1] ^ (1 << bit)  # Toggle bit
    print(f"  Toggle bit {bit} (0x{test[1]:02x}): ", end="", flush=True)
    try:
        device.send_feature_report(test)
        import time
        time.sleep(0.3)
        read_back = device.get_feature_report(0, 64)
        if read_back[1] != current[1]:
            print(f"✓ CHANGED to 0x{read_back[1]:02x} - THIS MIGHT BE THE LED!")
        else:
            print(f"✗ No change")
    except Exception as e:
        print(f"✗ Error: {e}")

print("\nTrying byte 2 (0x80)...")
for bit in range(8):
    test = bytearray(current)
    test[2] = test[2] ^ (1 << bit)
    print(f"  Toggle bit {bit} of byte 2 (0x{test[2]:02x}): ", end="", flush=True)
    try:
        device.send_feature_report(test)
        import time
        time.sleep(0.3)
        read_back = device.get_feature_report(0, 64)
        if read_back[2] != current[2]:
            print(f"✓ CHANGED to 0x{read_back[2]:02x} - THIS MIGHT BE THE LED!")
        else:
            print(f"✗ No change")
    except Exception as e:
        print(f"✗ Error: {e}")

device.close()

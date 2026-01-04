"""Discover which bits control which LEDs on the Flight Panel"""
import hid
import time

LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67

devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
device = hid.device()
device.open_path(devices[0]['path'])

print("Flight Panel LED Control Discovery")
print("=" * 60)
print("\nObserve the LED colors as we toggle bits.")
print("N LED initial: Red    -> Watch for Yellow")
print("L LED initial: Red")
print("R LED initial: Yellow")
print("\n" + "=" * 60 + "\n")

# Read baseline
baseline = device.get_feature_report(0, 64)
print(f"Baseline state: {' '.join(f'{b:02x}' for b in baseline[:4])}")
print(f"  Byte 1: 0x{baseline[1]:02x} = {baseline[1]:08b}")
print(f"  Byte 2: 0x{baseline[2]:02x} = {baseline[2]:08b}")
print(f"  Byte 3: 0x{baseline[3]:02x} = {baseline[3]:08b}")

print("\nTesting BYTE 1 bits (0x3c)...")
print("Which bit makes N LED change from Red to Yellow?\n")

for bit in range(8):
    test = bytearray(baseline)
    test[1] = test[1] ^ (1 << bit)  # Toggle bit
    
    mask = 1 << bit
    is_set = bool((baseline[1] >> bit) & 1)
    new_state = not is_set
    
    print(f"Bit {bit} ({mask:02x}): {baseline[1]:08b} -> {test[1]:08b} " + 
          f"(bit {'OFF→ON' if new_state else 'ON→OFF'})", end="  |  ")
    device.send_feature_report(test)
    
    response = input("Did N LED change? (y/n): ").strip().lower()
    if response == 'y':
        print("✓ THIS BIT CONTROLS N LED!")
        n_bit = bit
        n_on_value = new_state
        break
    else:
        print()
    
    time.sleep(0.3)

print("\n" + "=" * 60)
print("\nTesting BYTE 2 bits (0x80)...")
print("Which bit makes L or R LED change?\n")

baseline = device.get_feature_report(0, 64)

for bit in range(8):
    test = bytearray(baseline)
    test[2] = test[2] ^ (1 << bit)
    
    mask = 1 << bit
    is_set = bool((baseline[2] >> bit) & 1)
    new_state = not is_set
    
    print(f"Bit {bit} ({mask:02x}): {baseline[2]:08b} -> {test[2]:08b} " + 
          f"(bit {'OFF→ON' if new_state else 'ON→OFF'})", end="  |  ")
    device.send_feature_report(test)
    
    response = input("Did any LED change? (y/n): ").strip().lower()
    if response == 'y':
        print("✓ THIS BIT CONTROLS AN LED!")
    else:
        print()
    
    time.sleep(0.3)

print("\n" + "=" * 60)
print("\nReset to baseline...")
device.send_feature_report(baseline)

device.close()

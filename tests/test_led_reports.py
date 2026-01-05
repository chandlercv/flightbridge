import hid
import time

LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67

devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
device = hid.device()
device.open_path(devices[0]['path'])

print("All available feature reports:\n")

for report_id in range(6):
    try:
        data = device.get_feature_report(report_id, 64)
        print(f'Report ID {report_id}: {" ".join(f"{b:02x}" for b in data[:8])}')
    except Exception as e:
        print(f'Report ID {report_id}: Not available - {e}')

print("\n\nTrying to write to report ID 1 (output report)...\n")

# Try to modify and write to report ID 1
try:
    current = device.get_feature_report(1, 64)
    print(f'Current report ID 1: {" ".join(f"{b:02x}" for b in current)}')
    
    # Try setting various bytes
    for byte_idx in range(1, min(4, len(current))):
        test = bytearray(current)
        test[byte_idx] = 0xFF  # Set all bits
        print(f'  Trying to set byte {byte_idx} to 0xFF...', end=" ")
        try:
            result = device.send_feature_report(test)
            print(f"sent {result} bytes", end=" ")
            time.sleep(0.2)
            read_back = device.get_feature_report(1, 64)
            if read_back[byte_idx] == 0xFF:
                print(f"✓ CHANGED!")
            else:
                print(f"✗ Still 0x{read_back[byte_idx]:02x}")
        except Exception as e:
            print(f"✗ {e}")

except Exception as e:
    print(f'Error: {e}')

device.close()

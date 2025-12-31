"""Diagnostic script to inspect X-55 HID reports and device info.

Run this to see:
1. All HID devices connected
2. X-55 vendor/product IDs
3. Raw HID report data (useful for calibrating the parser)
"""
import hid
import struct
import time

def list_devices():
    """List all HID devices."""
    print("=" * 60)
    print("All HID Devices:")
    print("=" * 60)
    for device_info in hid.enumerate():
        print(f"\nVID:PID = 0x{device_info['vendor_id']:04X}:0x{device_info['product_id']:04X}")
        print(f"  Manufacturer: {device_info['manufacturer_string']}")
        print(f"  Product:      {device_info['product_string']}")
        print(f"  Serial:       {device_info['serial_number']}")
        print(f"  Path:         {device_info['path']}")

def find_x55_devices():
    """Find X-55 devices and return their info."""
    x55s = []
    for device_info in hid.enumerate():
        mfr = device_info['manufacturer_string'] or ""
        prod = device_info['product_string'] or ""
        if "saitek" in mfr.lower() or "x-55" in prod.lower() or "x55" in prod.lower():
            x55s.append(device_info)
    return x55s

def inspect_x55():
    """Open X-55 and dump raw HID reports."""
    x55s = find_x55_devices()
    
    if not x55s:
        print("\nNo X-55 devices found!")
        print("Check:")
        print("  1. Device is connected")
        print("  2. Drivers are installed")
        print("  3. Device is not already opened by another process")
        return
    
    print("\n" + "=" * 60)
    print("Found X-55 Device(s):")
    print("=" * 60)
    
    for i, dev_info in enumerate(x55s):
        print(f"\n[Device {i}]")
        print(f"VID:PID = 0x{dev_info['vendor_id']:04X}:0x{dev_info['product_id']:04X}")
        print(f"Manufacturer: {dev_info['manufacturer_string']}")
        print(f"Product:      {dev_info['product_string']}")
        print(f"Serial:       {dev_info['serial_number']}")
        
        try:
            device = hid.device()
            device.open_path(dev_info['path'])
            
            print(f"\n[Raw HID Reports - next 20 reports (5 seconds)]")
            print("-" * 60)
            
            start = time.time()
            count = 0
            while time.time() - start < 5.0 and count < 20:
                data = device.read(64, timeout_ms=100)
                if data:
                    count += 1
                    # Print as hex and attempt some structure
                    hex_str = " ".join(f"{b:02X}" for b in data)
                    print(f"Report {count}: {hex_str}")
                    
                    # Try to parse as signed 16-bit values
                    try:
                        if len(data) >= 8:
                            vals = struct.unpack_from('<hhhh', data, 0)
                            print(f"  → As s16[4]: {vals}")
                    except:
                        pass
            
            device.close()
            
        except Exception as e:
            print(f"  Error reading device: {e}")

if __name__ == "__main__":
    print("X-55 HID Diagnostic Tool\n")
    
    list_devices()
    inspect_x55()
    
    print("\n" + "=" * 60)
    print("Tips:")
    print("  - If you see your X-55, note the VID:PID")
    print("  - Raw reports help calibrate the parser in x55_hidapi.py")
    print("  - Move sticks/press buttons to see report changes")
    print("=" * 60)

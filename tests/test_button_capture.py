#!/usr/bin/env python3
"""
Capture raw X-55 HID reports and log them when input changes.
Run this, don't touch anything for 3 seconds, then press various buttons.
"""
import logging
import time
import sys
import threading

# Setup logging to be very verbose
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

try:
    import hid
except ImportError:
    print("ERROR: hidapi not installed. Run: pip install hidapi")
    sys.exit(1)

# Saitek X-55
X55_VID = 0x0738
X55_PID = 0x2215

def main():
    device = hid.device()
    try:
        device.open(X55_VID, X55_PID)
    except OSError:
        print("ERROR: X-55 not found")
        sys.exit(1)
    
    print(f"X-55 opened: {device.get_product_string()}")
    print("\nWaiting for 3 seconds for baseline...")
    time.sleep(3)
    
    print("Now capturing reports. Press buttons and move controls.")
    print("Press Ctrl+C to stop.\n")
    
    baseline_report = None
    report_count = 0
    
    try:
        while True:
            data = device.read(64, timeout_ms=100)
            
            if data:
                report_count += 1
                
                if baseline_report is None:
                    baseline_report = bytes(data)
                    print(f"[{report_count}] Baseline: {' '.join(f'{b:02X}' for b in data)}")
                    continue
                
                # Check if this report is different from baseline
                if bytes(data) != baseline_report:
                    diff_indices = [i for i in range(len(data)) if data[i] != baseline_report[i]]
                    print(f"[{report_count}] DIFFERENT! Changed bytes: {diff_indices}")
                    print(f"       New: {' '.join(f'{b:02X}' for b in data)}")
                    print(f"       Old: {' '.join(f'{b:02X}' for b in baseline_report)}")
                    print(f"       Diffs: {' '.join(f'[{i}]:{baseline_report[i]:02X}→{data[i]:02X}' for i in diff_indices)}")
                    print()
                
                time.sleep(0.05)  # 50ms between checks
    
    except KeyboardInterrupt:
        print("\n\nCapture stopped.")
    finally:
        device.close()

if __name__ == "__main__":
    main()

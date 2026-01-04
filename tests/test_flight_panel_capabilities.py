"""Test script to determine Flight Panel HID capabilities

This script probes the Flight Panel to understand:
- Whether it supports feature reports
- What HID reports it sends and when
- The exact data format
- Whether it can be queried for current state or only sends on change
"""
import sys
import time
import logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)

try:
    import hid
    HAS_HID = True
except ImportError:
    HAS_HID = False
    LOG.error("hidapi not installed. Install with: pip install hidapi")
    sys.exit(1)

LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67


def test_device_discovery():
    """Find the Flight Panel and list all HID devices."""
    LOG.info("=" * 60)
    LOG.info("DEVICE DISCOVERY")
    LOG.info("=" * 60)
    
    devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
    
    if not devices:
        LOG.warning("No Flight Panel found (VID:%04x, PID:%04x)", LOGITECH_VID, FLIGHT_PANEL_PID)
        LOG.info("All connected HID devices:")
        all_devices = hid.enumerate()
        for dev in all_devices[:10]:  # Show first 10
            LOG.info("  VID:%04x PID:%04x - %s", dev['vendor_id'], dev['product_id'], dev['product_string'])
        return None
    
    LOG.info("Found %d Flight Panel device(s):", len(devices))
    for i, dev in enumerate(devices):
        LOG.info("Device %d:", i)
        LOG.info("  Path: %s", dev['path'])
        LOG.info("  VID:PID: %04x:%04x", dev['vendor_id'], dev['product_id'])
        LOG.info("  Manufacturer: %s", dev['manufacturer_string'])
        LOG.info("  Product: %s", dev['product_string'])
        LOG.info("  Serial: %s", dev['serial_number'])
        LOG.info("  Interface: %d", dev['interface_number'])
    
    return devices[0]


def test_feature_report(device):
    """Try to read feature reports from the device."""
    LOG.info("\n" + "=" * 60)
    LOG.info("FEATURE REPORT TEST")
    LOG.info("=" * 60)
    
    try:
        # Try reading feature report with report ID 0
        data = device.get_feature_report(0, 64)
        LOG.info("✓ get_feature_report(0, 64) succeeded")
        LOG.info("  Data length: %d bytes", len(data))
        LOG.info("  Raw data: %s", ' '.join(f"{b:02x}" for b in data))
        return True
    except Exception as e:
        LOG.warning("✗ get_feature_report(0) failed: %s", e)
    
    # Try with report ID 1
    try:
        data = device.get_feature_report(1, 64)
        LOG.info("✓ get_feature_report(1, 64) succeeded")
        LOG.info("  Data length: %d bytes", len(data))
        LOG.info("  Raw data: %s", ' '.join(f"{b:02x}" for b in data))
        return True
    except Exception as e:
        LOG.warning("✗ get_feature_report(1) failed: %s", e)
    
    LOG.info("No feature reports available")
    return False


def test_input_reports(device, duration=5, timeout_ms=100):
    """Monitor for input reports from the device."""
    LOG.info("\n" + "=" * 60)
    LOG.info("INPUT REPORT TEST (monitoring for %d seconds)", duration)
    LOG.info("=" * 60)
    LOG.info("Toggling switches/buttons on the Flight Panel now...")
    
    start = time.time()
    report_count = 0
    last_data = None
    
    while time.time() - start < duration:
        try:
            data = device.read(64, timeout_ms=timeout_ms)
            if data:
                report_count += 1
                LOG.info("Report #%d:", report_count)
                LOG.info("  Length: %d bytes", len(data))
                LOG.info("  Raw: %s", ' '.join(f"{b:02x}" for b in data))
                
                # Try to decode as bit flags
                LOG.info("  Bytes as bits:")
                for byte_idx, byte_val in enumerate(data):
                    bits = ' '.join(str((byte_val >> (7 - i)) & 1) for i in range(8))
                    LOG.info("    Byte %d (0x%02x): %s", byte_idx, byte_val, bits)
                
                if last_data and last_data != data:
                    LOG.info("  ⚠ CHANGED from previous report")
                last_data = data
        except Exception as e:
            # Timeout is expected, ignore
            pass
    
    if report_count == 0:
        LOG.warning("No input reports received. Check that switches are changing state.")
    else:
        LOG.info("Received %d input reports in %d seconds", report_count, duration)
    
    return report_count > 0


def test_nonblocking_read(device):
    """Test immediate non-blocking read with very short timeout."""
    LOG.info("\n" + "=" * 60)
    LOG.info("NON-BLOCKING READ TEST")
    LOG.info("=" * 60)
    
    try:
        data = device.read(64, timeout_ms=1)
        if data:
            LOG.info("✓ Immediate read succeeded (device had pending data)")
            LOG.info("  Data: %s", ' '.join(f"{b:02x}" for b in data))
        else:
            LOG.info("✓ Read timeout with no pending data (expected if no switch changed)")
    except Exception as e:
        LOG.error("✗ Read failed: %s", e)


def test_device_info(device):
    """Get device info and capabilities."""
    LOG.info("\n" + "=" * 60)
    LOG.info("DEVICE INFO & CAPABILITIES")
    LOG.info("=" * 60)
    
    try:
        info = device.get_info()
        if info:
            LOG.info("Device info available")
            # Most of the info is already from enumerate, but try to get more
    except Exception as e:
        LOG.debug("get_info() not available: %s", e)
    
    LOG.info("Note: This device appears to be a Saitek/Logitech Flight Switch Panel")
    LOG.info("Expected behavior: Event-driven HID device (reports on change only)")
    LOG.info("Typical report format: 8 bytes for ~12-20 switches/buttons")


def main():
    LOG.info("Flight Panel HID Capabilities Test\n")
    
    # Discover device
    dev_info = test_device_discovery()
    if not dev_info:
        LOG.error("Cannot proceed without device")
        return
    
    # Open device
    device = hid.device()
    try:
        device.open_path(dev_info['path'])
        LOG.info("\n✓ Device opened successfully")
    except Exception as e:
        LOG.error("✗ Failed to open device: %s", e)
        return
    
    try:
        # Run tests
        test_device_info(device)
        test_feature_report(device)
        test_nonblocking_read(device)
        test_input_reports(device, duration=10)
        
        # Summary
        LOG.info("\n" + "=" * 60)
        LOG.info("SUMMARY")
        LOG.info("=" * 60)
        LOG.info("Based on the above tests:")
        LOG.info("1. Does device support feature reports? Check above")
        LOG.info("2. Can we query current state? Check feature report results")
        LOG.info("3. When does device send data? Check input reports")
        LOG.info("4. What is the report format? Check raw hex data above")
        
    finally:
        device.close()


if __name__ == "__main__":
    main()

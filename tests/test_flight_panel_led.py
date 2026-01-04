"""Test script to determine Flight Panel LED control capabilities

The Saitek/Logitech Flight Switch Panel has LEDs for certain features:
- Landing gear indicator LED
- Potentially other status LEDs

This script tests how to control them via HID output/feature reports.
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


def test_led_control():
    """Test LED control on Flight Panel."""
    LOG.info("=" * 60)
    LOG.info("FLIGHT PANEL LED CONTROL TEST")
    LOG.info("=" * 60)
    
    # Find device
    devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
    if not devices:
        LOG.error("Flight Panel not found")
        return
    
    device = hid.device()
    device.open_path(devices[0]['path'])
    LOG.info("Device opened")
    
    # First, let's read the current feature report again
    try:
        data = device.get_feature_report(0, 64)
        LOG.info("Current feature report (report ID 0): %s", ' '.join(f"{b:02x}" for b in data))
    except Exception as e:
        LOG.warning("get_feature_report(0) failed: %s", e)
    
    # Try other report IDs
    for report_id in [1, 2, 3, 4, 5]:
        try:
            data = device.get_feature_report(report_id, 64)
            LOG.info("Feature report ID %d: %s", report_id, ' '.join(f"{b:02x}" for b in data))
        except Exception as e:
            LOG.debug("Feature report ID %d not available: %s", report_id, e)
    
    LOG.info("\nAttempting to set feature reports to control LEDs...")
    
    # Test writing feature reports (landing gear LED is typically controlled this way)
    # Common patterns:
    # - Report ID 0, byte for LED state
    # - Landing gear LED is usually bit in a feature report
    
    test_reports = [
        (0, bytearray([0x00, 0x3c, 0x40, 0x04])),  # Current state
        (0, bytearray([0x00, 0x3c, 0x40, 0x84])),  # Try setting bit 7 of byte 3
        (0, bytearray([0x00, 0x3c, 0x40, 0x05])),  # Try setting bit 0 of byte 3
        (0, bytearray([0x00, 0x3c, 0xc0, 0x04])),  # Try setting bit 7 of byte 1
    ]
    
    for report_id, data in test_reports:
        try:
            LOG.info("Attempting to set feature report ID %d: %s", report_id, ' '.join(f"{b:02x}" for b in data))
            result = device.send_feature_report(data)
            LOG.info("  ✓ Success! Result: %d", result)
            
            # Read back to see if it changed
            try:
                read_back = device.get_feature_report(report_id, 64)
                LOG.info("  Read back: %s", ' '.join(f"{b:02x}" for b in read_back))
            except Exception as e:
                LOG.debug("  Could not read back: %s", e)
            
            time.sleep(0.5)
        except Exception as e:
            LOG.debug("  ✗ Failed: %s", e)
    
    # Try write operations (less common for HID input devices)
    LOG.info("\nAttempting to write output reports...")
    test_writes = [
        bytearray([0x00, 0x3c, 0x40, 0x84]),
        bytearray([0x00, 0x3c, 0x40, 0x05]),
        bytearray([0x00, 0x3c, 0xc0, 0x04]),
    ]
    
    for data in test_writes:
        try:
            LOG.info("Attempting to write: %s", ' '.join(f"{b:02x}" for b in data))
            result = device.write(data)
            LOG.info("  ✓ Success! Result: %d", result)
            time.sleep(0.5)
        except Exception as e:
            LOG.debug("  ✗ Failed: %s", e)
    
    # Research note: Saitek panels typically use specific bits for LEDs
    # Landing gear LED is usually controlled via feature report
    # The pattern is typically:
    # - Query current state with get_feature_report
    # - Modify the appropriate bits
    # - Send back with send_feature_report
    
    LOG.info("\n" + "=" * 60)
    LOG.info("RESEARCH NOTES")
    LOG.info("=" * 60)
    LOG.info("Saitek/Logitech Flight Panels typically control LEDs via:")
    LOG.info("1. Feature reports (most common) - use send_feature_report()")
    LOG.info("2. The landing gear LED is usually bit 7 (0x80) of a specific byte")
    LOG.info("3. You typically:")
    LOG.info("   - Read current state: get_feature_report(0, 64)")
    LOG.info("   - Modify LED bits")
    LOG.info("   - Write back: send_feature_report(modified_data)")
    LOG.info("\nBased on test output above, we can determine which bit/byte controls the LED")
    
    device.close()


if __name__ == "__main__":
    test_led_control()

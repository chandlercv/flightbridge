"""Helper module to control Flight Panel LEDs"""
import logging
import hid
import threading
import time

LOG = logging.getLogger("flightbridge.flight_panel_leds")

LOGITECH_VID = 0x06a3
FLIGHT_PANEL_PID = 0x0d67

# LED bit mappings discovered via testing
# Byte 1: N position light
#   Bit 0 (0x01): N light ON/OFF
# Byte 2: L/R position lights  
#   Bit 0 (0x01): L light ON/OFF (or combined L/R)

N_LIGHT_BIT = 0x01  # Byte 1, bit 0
L_LIGHT_BIT = 0x01  # Byte 2, bit 0 (for L position light)
# TODO: Discover R light control


class FlightPanelLEDControl:
    """Control Flight Panel LEDs via HID feature reports"""
    
    def __init__(self):
        self._device = None
        self._lock = threading.Lock()
        self._current_state = None
        self._last_report = None
        
    def connect(self):
        """Open connection to Flight Panel"""
        try:
            devices = hid.enumerate(LOGITECH_VID, FLIGHT_PANEL_PID)
            if not devices:
                LOG.warning("Flight Panel not found for LED control")
                return False
            
            self._device = hid.device()
            self._device.open_path(devices[0]['path'])
            
            # Get initial state
            self._current_state = self._device.get_feature_report(0, 64)
            self._last_report = bytearray(self._current_state)
            LOG.info("Flight Panel LED control connected")
            return True
        except Exception as e:
            LOG.error("Failed to connect for LED control: %s", e)
            self._device = None
            return False
    
    def disconnect(self):
        """Close connection"""
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
    
    def set_n_light(self, on: bool):
        """Control N position light"""
        if not self._device:
            return False
        
        with self._lock:
            try:
                report = bytearray(self._last_report)
                
                if on:
                    report[1] |= N_LIGHT_BIT  # Set bit
                else:
                    report[1] &= ~N_LIGHT_BIT  # Clear bit
                
                self._device.send_feature_report(report)
                self._last_report = report
                LOG.debug("N light: %s", "ON" if on else "OFF")
                return True
            except Exception as e:
                LOG.error("Failed to set N light: %s", e)
                return False
    
    def set_l_light(self, on: bool):
        """Control L position light"""
        if not self._device:
            return False
        
        with self._lock:
            try:
                report = bytearray(self._last_report)
                
                if on:
                    report[2] |= L_LIGHT_BIT  # Set bit
                else:
                    report[2] &= ~L_LIGHT_BIT  # Clear bit
                
                self._device.send_feature_report(report)
                self._last_report = report
                LOG.debug("L light: %s", "ON" if on else "OFF")
                return True
            except Exception as e:
                LOG.error("Failed to set L light: %s", e)
                return False
    
    def set_landing_gear(self, down: bool):
        """Set landing gear lights based on position (proxy for N+L lights)"""
        # Typically both N and L light up when gear is down
        self.set_n_light(down)
        self.set_l_light(down)


# Test/demo
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    leds = FlightPanelLEDControl()
    if leds.connect():
        print("Testing LED control...")
        
        print("N light ON")
        leds.set_n_light(True)
        time.sleep(1)
        
        print("N light OFF")
        leds.set_n_light(False)
        time.sleep(1)
        
        print("L light ON")
        leds.set_l_light(True)
        time.sleep(1)
        
        print("L light OFF")
        leds.set_l_light(False)
        time.sleep(1)
        
        print("Both lights ON (gear down)")
        leds.set_landing_gear(True)
        time.sleep(1)
        
        print("Both lights OFF (gear up)")
        leds.set_landing_gear(False)
        
        leds.disconnect()

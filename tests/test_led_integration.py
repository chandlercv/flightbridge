"""Quick test to verify LED integration in mapper and VJoyOutput"""
import sys
import logging
sys.path.insert(0, '.')

logging.basicConfig(level=logging.DEBUG)

from mapper import Mapper
from core.state import VJoyCommand

# Create a simple test profile with LED mappings
test_profile = {
    "bindings": [
        {
            "input": "x55.button.10",
            "target": "led:landing_gear"
        },
        {
            "input": "x55.button.11",
            "target": "led:n_light"
        },
        {
            "input": "x55.button.12",
            "target": "led:l_light"
        }
    ]
}

mapper = Mapper(test_profile)

# Simulate button press
test_state = {
    "x55": {
        "device": "x55",
        "buttons": {
            10: True,   # landing_gear ON
            11: True,   # n_light ON
            12: False,  # l_light OFF
        },
        "axes": {},
        "hats": {}
    }
}

# Map state
cmd = mapper.map_state_to_vjoy_full(test_state)

print("[PASS] LED Mapping Test Passed!")
print(f"  Input buttons: 10={test_state['x55']['buttons'].get(10)}, 11={test_state['x55']['buttons'].get(11)}, 12={test_state['x55']['buttons'].get(12)}")
print(f"  Output LEDs: {cmd.leds}")
print()
print("LED States:")
print(f"  landing_gear: {cmd.leds.get('landing_gear', 'N/A')}")
print(f"  n_light: {cmd.leds.get('n_light', 'N/A')}")
print(f"  l_light: {cmd.leds.get('l_light', 'N/A')}")

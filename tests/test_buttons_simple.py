"""Simple test to capture raw HID and buttons"""
import logging
logging.basicConfig(level=logging.INFO)

from devices.x55_hidapi import X55Reader

reader = X55Reader()

print("\nPress some buttons on the X-55. Watch for which buttons show as pressed.")
print("(This will run for 10 seconds)\n")

count = [0]

def on_state(state):
    count[0] += 1
    if count[0] % 30 == 0:  # Every ~0.25 seconds at 120Hz
        buttons = state.get('buttons', {})
        pressed = [i for i, v in buttons.items() if v]
        if pressed:
            print(f"Pressed buttons: {pressed}")
        else:
            print("No buttons pressed")

reader.subscribe(on_state)
reader.start()

import time
try:
    time.sleep(10)
except KeyboardInterrupt:
    pass
finally:
    reader.stop()
    print("\nDone!")

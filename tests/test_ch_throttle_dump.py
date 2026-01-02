"""Debug module for CH Throttle device

Displays raw joystick data and normalized throttle axis output.
Useful for debugging throttle calibration and button mapping.
"""
import time
import traceback

try:
    import pygame
    pygame.init()
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    print('joystick count:', count)
    if count == 0:
        print('No joysticks found')
        raise SystemExit(0)

    # Find CH Throttle or use first joystick
    ch_throttle = None
    for i in range(count):
        js = pygame.joystick.Joystick(i)
        js.init()
        name = js.get_name() or ""
        print(f'[{i}] {name}')
        if "ch" in name.lower() or "throttle" in name.lower() or "arduino" in name.lower():
            ch_throttle = js
            print(f'  -> Selected as CH Throttle')
    
    if ch_throttle is None:
        ch_throttle = pygame.joystick.Joystick(0)
        ch_throttle.init()
        print(f'Using first joystick as CH Throttle')
    
    print('\nDevice info:')
    print(f'  name: {ch_throttle.get_name()}')
    print(f'  axes: {ch_throttle.get_numaxes()}')
    print(f'  buttons: {ch_throttle.get_numbuttons()}')
    print(f'  hats: {ch_throttle.get_numhats()}')
    print('\nReading throttle axis (normalized 0.0-1.0) and buttons...\n')

    while True:
        pygame.event.pump()
        
        # Read and normalize throttle axis (axis 0: -1.0 to 1.0 -> 0.0 to 1.0)
        raw_throttle = ch_throttle.get_axis(0)
        throttle = (raw_throttle + 1.0) / 2.0
        
        # Read buttons 0-11
        buttons = [ch_throttle.get_button(i) for i in range(min(12, ch_throttle.get_numbuttons()))]
        
        t = time.time()
        print(f"{t:.3f} throttle_raw: {raw_throttle:7.4f} throttle_norm: {throttle:6.4f} buttons: {buttons}")
        time.sleep(0.2)
except Exception:
    traceback.print_exc()

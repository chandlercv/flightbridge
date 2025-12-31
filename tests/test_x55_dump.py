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

    js = pygame.joystick.Joystick(0)
    js.init()
    print('name:', js.get_name())
    print('axes:', js.get_numaxes(), 'buttons:', js.get_numbuttons(), 'hats:', js.get_numhats())

    while True:
        pygame.event.pump()
        axes = [js.get_axis(i) for i in range(js.get_numaxes())]
        buttons = [js.get_button(i) for i in range(js.get_numbuttons())]
        hats = [js.get_hat(i) for i in range(js.get_numhats())]
        t = time.time()
        print(f"{t:.3f} axes: {[f'{a:.6f}' for a in axes]} buttons: {buttons} hats: {hats}")
        time.sleep(0.2)
except Exception:
    traceback.print_exc()

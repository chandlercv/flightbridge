import pyvjoy
import time

print("Testing direct wAxisX / wAxisY assignment...\n")

d = pyvjoy.VJoyDevice(1)

print("--- Test: Direct wAxisX and wAxisY assignment ---")
try:
    for i in range(5):
        print(f"\n{i}: Setting X to MIN (0), Y to MIN (0)")
        d.data.wAxisX = 0
        d.data.wAxisY = 0
        d.update()
        time.sleep(0.5)
        
        print(f"{i}: Setting X to MAX (0x8000), Y to MAX (0x8000)")
        d.data.wAxisX = 0x8000
        d.data.wAxisY = 0x8000
        d.update()
        time.sleep(0.5)
        
    print("\nDone!")
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()

print("\nDid the Monitor X/Y axes move dramatically?")

# flightbridge

Bridge inputs from Logitech flight panels and Saitek X-55 (DirectInput) to vJoy using Python.

Quickstart:
- Install vJoy via winget (64-bit) and create a virtual device (axes, buttons, POV):
    winget install ShaulEizikovich.vJoyDeviceDriver
    # If the DLL is not at the default path, update it in vjoy/output.py.
- Install hidhide `winget install Nefarius.HidHide`
- Install Python deps (recommended):
  create venv
  pip install requirements.txt
- Run:
  python app.py --profile config/mappings/elite_dangerous.yaml

This repo contains initial scaffolding (readers, mapper, vjoy output) — more implementation coming.

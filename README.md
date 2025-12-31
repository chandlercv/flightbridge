# flightbridge

Bridge inputs from Logitech flight panels and Saitek X-55 (DirectInput) to vJoy using Python.

Quickstart:
- Install vJoy and create a virtual device (axes, buttons, POV) via vJoy Config.
- Install Python deps (recommended):
  pip install pyvjoy pygame pyyaml
- Run:
  python app.py --profile config/mappings/elite_dangerous.yaml

This repo contains initial scaffolding (readers, mapper, vjoy output) — more implementation coming.

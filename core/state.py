"""State models and lightweight DTOs"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class DeviceState:
    device: str
    axes: Dict[int, float] = field(default_factory=dict)
    buttons: Dict[int, bool] = field(default_factory=dict)
    hats: Dict[int, Tuple[int, int]] = field(default_factory=dict)


@dataclass
class VJoyCommand:
    axes: Dict[str, float] = field(default_factory=dict)  # axis name -> -1..1
    buttons: Dict[int, bool] = field(default_factory=dict)  # button id -> state
    povs: Dict[int, int] = field(default_factory=dict)  # pov id -> degrees or -1
    keys: Dict[str, bool] = field(default_factory=dict)  # key name -> pressed state
    leds: Dict[str, bool] = field(default_factory=dict)  # led name -> on/off (e.g., "n_light", "l_light")

"""Mapping engine: load YAML profiles and map DeviceState -> VJoyCommand"""
import yaml
import logging
import time
from core.state import VJoyCommand

LOG = logging.getLogger("flightbridge.mapper")


class Mapper:
    def __init__(self, profile: dict):
        self.profile = profile
        self._prev_state = {}  # Track previous state for toggle mode detection
        self._pulse_timers = {}  # Track active pulses: {button_id: end_time}

    @classmethod
    def load_profile(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data)

    def map_state_to_vjoy(self, state) -> VJoyCommand:
        # Very small reference implementation: look for axis bindings and button bindings
        cmd = VJoyCommand()
        bindings = self.profile.get("bindings", [])
        # device state is a simple dict with `device` key for now
        device_name = state.get("device")
        for b in bindings:
            # Support both 'input' (single) and 'inputs' (multiple)
            src = b.get("input")
            src_list = b.get("inputs", [src] if src else [])
            tgt = b.get("target")  # e.g. 'axis:AXIS_X' or 'button:1'
            props = b.get("props", {})
            
            # Process single inputs
            if src and not b.get("inputs"):
                if not src or not tgt:
                    LOG.debug("skipping incomplete binding: %s", b)
                    continue
                try:
                    if src.startswith("x55.axes") and device_name == "x55":
                        idx = int(src.split(".")[-1])
                        val = state.get("axes", {}).get(idx, 0.0)
                        val = float(val)
                        if props.get("invert"):
                            val = -val
                        val = val * float(props.get("scale", 1.0))
                        # clamp
                        val = max(-1.0, min(1.0, val))
                        if tgt.startswith("axis:"):
                            axis_name = tgt.split(":", 1)[1]
                            cmd.axes[axis_name] = val
                    if src.startswith("x55.button") and device_name == "x55":
                        idx = int(src.split(".")[-1])
                        st = bool(state.get("buttons", {}).get(idx, False))
                        if tgt.startswith("button:"):
                            btn_id = int(tgt.split(":", 1)[1])
                            cmd.buttons[btn_id] = st
                    if src.startswith("x55.hat") and device_name == "x55":
                        idx = int(src.split(".")[-1])
                        hat_val = state.get("hats", {}).get(idx, (-1, -1))
                        # pygame hat is tuple (x, y) like (-1, -1), (0, 1), (1, 0), etc.
                        # convert to degrees: -1 = centered, 0 = up, 90 = right, 180 = down, 270 = left
                        if hat_val == (0, 0):
                            deg = -1  # centered
                        elif hat_val == (0, 1):
                            deg = 0  # up
                        elif hat_val == (1, 1):
                            deg = 45  # up-right
                        elif hat_val == (1, 0):
                            deg = 90  # right
                        elif hat_val == (1, -1):
                            deg = 135  # down-right
                        elif hat_val == (0, -1):
                            deg = 180  # down
                        elif hat_val == (-1, -1):
                            deg = 225  # down-left
                        elif hat_val == (-1, 0):
                            deg = 270  # left
                        elif hat_val == (-1, 1):
                            deg = 315  # up-left
                        else:
                            deg = -1  # default centered
                        if tgt.startswith("pov:"):
                            pov_id = int(tgt.split(":", 1)[1])
                            cmd.povs[pov_id] = deg
                            LOG.debug("mapped hat %s -> pov %d (%s -> %d°)", hat_val, pov_id, hat_val, deg)
                    if src.startswith("flightpanel.switch") and device_name == "flightpanel":
                        idx = int(src.split(".")[-1])
                        st = bool(state.get("buttons", {}).get(idx, False))
                        
                        # Get mapping mode and pulse duration
                        mode = props.get("mode", "direct")  # "direct" or "toggle"
                        pulse_ms = props.get("pulse_ms", 100)  # default 100ms pulse
                        trigger = props.get("trigger", "on_change")  # "on_press", "on_release", or "on_change"
                        
                        if tgt.startswith("button:"):
                            btn_id = int(tgt.split(":", 1)[1])
                            state_key = f"flightpanel.switch.{idx}"
                            
                            if mode == "toggle":
                                # Toggle mode: pulse on state change
                                prev_st = self._prev_state.get(state_key, None)
                                
                                if prev_st is not None and prev_st != st:
                                    # State changed - check trigger condition
                                    should_trigger = False
                                    if trigger == "on_change":
                                        should_trigger = True
                                    elif trigger == "on_press" and st is True:
                                        should_trigger = True
                                    elif trigger == "on_release" and st is False:
                                        should_trigger = True
                                    
                                    if should_trigger:
                                        self._pulse_timers[btn_id] = time.time() + (pulse_ms / 1000.0)
                                        LOG.debug("flightpanel.switch.%d changed %s->%s (trigger:%s), pulsing button:%d for %dms", 
                                                 idx, prev_st, st, trigger, btn_id, pulse_ms)
                                
                                self._prev_state[state_key] = st
                            else:
                                # Direct mode: store state for later application
                                self._prev_state[state_key] = st
                    if src.startswith("ch_throttle.axes") and device_name == "ch_throttle":
                        idx = int(src.split(".")[-1])
                        val = state.get("axes", {}).get(idx, 0.0)
                        val = float(val)
                        if props.get("invert"):
                            val = -val
                        val = val * float(props.get("scale", 1.0))
                        # clamp
                        val = max(-1.0, min(1.0, val))
                        if tgt.startswith("axis:"):
                            axis_name = tgt.split(":", 1)[1]
                            cmd.axes[axis_name] = val
                    if src.startswith("ch_throttle.button") and device_name == "ch_throttle":
                        idx = int(src.split(".")[-1])
                        st = bool(state.get("buttons", {}).get(idx, False))
                        if tgt.startswith("button:"):
                            btn_id = int(tgt.split(":", 1)[1])
                            cmd.buttons[btn_id] = st
                    if src.startswith("flightpanel.axis") and device_name == "flightpanel":
                        idx = int(src.split(".")[-1])
                        val = state.get("axes", {}).get(idx, 0.0)
                        val = float(val)
                        if props.get("invert"):
                            val = -val
                        val = val * float(props.get("scale", 1.0))
                        # clamp
                        val = max(-1.0, min(1.0, val))
                        if tgt.startswith("axis:"):
                            axis_name = tgt.split(":", 1)[1]
                            cmd.axes[axis_name] = val
                except Exception:
                    LOG.exception("mapping error for binding %s", b)
            
            # Process multiple inputs (AND logic)
            elif src_list and tgt:
                try:
                    # Only process flight panel multi-input bindings when flight panel event arrives
                    if device_name == "flightpanel":
                        mode = props.get("mode", "direct")
                        
                        # Update state for any flight panel inputs in this binding
                        for src_item in src_list:
                            if src_item.startswith("flightpanel.switch"):
                                idx = int(src_item.split(".")[-1])
                                st = bool(state.get("buttons", {}).get(idx, False))
                                state_key = f"flightpanel.switch.{idx}"
                                self._prev_state[state_key] = st
                except Exception:
                    LOG.exception("mapping error for multi-input binding %s", b)
        
        # Check active pulse timers and apply them to the command
        # This runs on EVERY call, not just when flight panel events arrive
        current_time = time.time()
        expired_timers = []
        for btn_id, end_time in self._pulse_timers.items():
            if current_time < end_time:
                cmd.buttons[btn_id] = True
            else:
                expired_timers.append(btn_id)
        
        # Clean up expired timers
        for btn_id in expired_timers:
            del self._pulse_timers[btn_id]
        
        # Apply direct mode buttons from stored state (single and multiple inputs)
        # These need to persist even when no flight panel event is sent
        for b in bindings:
            src = b.get("input")
            src_list = b.get("inputs", [src] if src else [])
            tgt = b.get("target")
            props = b.get("props", {})
            
            if tgt and tgt.startswith("button:"):
                mode = props.get("mode", "direct")
                if mode == "direct":
                    btn_id = int(tgt.split(":", 1)[1])
                    
                    # Single input direct mode
                    if src and not b.get("inputs"):
                        if src.startswith("flightpanel.switch"):
                            idx = int(src.split(".")[-1])
                            state_key = f"flightpanel.switch.{idx}"
                            if state_key in self._prev_state:
                                cmd.buttons[btn_id] = self._prev_state[state_key]
                    
                    # Multiple inputs direct mode (AND logic)
                    elif src_list:
                        all_true = True
                        for src_item in src_list:
                            if src_item.startswith("flightpanel.switch"):
                                idx = int(src_item.split(".")[-1])
                                state_key = f"flightpanel.switch.{idx}"
                                # If state not yet set, default to False
                                if state_key not in self._prev_state:
                                    all_true = False
                                    break
                                if not self._prev_state[state_key]:
                                    all_true = False
                                    break
                        cmd.buttons[btn_id] = all_true
                        LOG.debug("multi-input AND condition for button:%d = %s", btn_id, all_true)
        
        LOG.debug("mapped state -> %s", cmd)
        return cmd

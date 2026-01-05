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

    @staticmethod
    def _key_names_from_target(tgt: str):
        """Return list of key names from a target like 'key:space' or 'key:shift key:c'."""
        if not tgt.startswith("key:"):
            return []
        remainder = tgt.split(":", 1)[1]
        key_names = []
        for token in remainder.split():
            if not token:
                continue
            # Allow optional repeated key: prefixes in the list
            if token.startswith("key:"):
                token = token.split(":", 1)[1]
            if token:
                key_names.append(token)
        return key_names

    def _refresh_state_from_event(self, src_item: str, device_name: str, state: dict):
        """Update cached state for a source if the current event owns it."""
        if src_item.startswith("x55.button") and device_name == "x55":
            idx = int(src_item.split(".")[-1])
            st = bool(state.get("buttons", {}).get(idx, False))
            self._prev_state[src_item] = st
            return st, True
        if (src_item.startswith("flightpanel.switch") or src_item.startswith("flightpanel.button")) and device_name == "flightpanel":
            idx = int(src_item.split(".")[-1])
            st = bool(state.get("buttons", {}).get(idx, False))
            self._prev_state[src_item] = st
            return st, True
        if src_item.startswith("ch_throttle.button") and device_name == "ch_throttle":
            idx = int(src_item.split(".")[-1])
            st = bool(state.get("buttons", {}).get(idx, False))
            self._prev_state[src_item] = st
            return st, True
        return self._prev_state.get(src_item, False), False

    @classmethod
    def load_profile(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data)

    def map_state_to_vjoy_full(self, all_states: dict) -> VJoyCommand:
        """Map accumulated state from all devices to vJoy command"""
        cmd = VJoyCommand()
        
        # Process each device's state
        for device_name, state in all_states.items():
            state_with_device = {**state, "device": device_name}
            device_cmd = self.map_state_to_vjoy(state_with_device)
            
            # Merge commands (buttons, axes, povs, keys, leds)
            cmd.buttons.update(device_cmd.buttons)
            cmd.axes.update(device_cmd.axes)
            cmd.povs.update(device_cmd.povs)
            cmd.keys.update(device_cmd.keys)
            cmd.leds.update(device_cmd.leds)
        
        return cmd

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
                        self._prev_state[src] = st
                        if tgt.startswith("button:"):
                            btn_id = int(tgt.split(":", 1)[1])
                            cmd.buttons[btn_id] = st
                        elif tgt.startswith("key:"):
                            for key_name in self._key_names_from_target(tgt):
                                cmd.keys[key_name] = st
                        elif tgt.startswith("led:"):
                            led_name = tgt.split(":", 1)[1]
                            cmd.leds[led_name] = st
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
                                
                                # Trigger if state changed (or if this is the first time and state is True)
                                if prev_st != st:
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
                        elif tgt.startswith("key:"):
                            # Keyboard key support for flight panel switches
                            key_names = self._key_names_from_target(tgt)
                            state_key = f"flightpanel.switch.{idx}"
                            
                            if mode == "toggle":
                                # Toggle mode: pulse on state change
                                prev_st = self._prev_state.get(state_key, None)
                                
                                # Trigger if state changed (or if this is the first time and state is True)
                                if prev_st != st:
                                    # State changed - check trigger condition
                                    should_trigger = False
                                    if trigger == "on_change":
                                        should_trigger = True
                                    elif trigger == "on_press" and st is True:
                                        should_trigger = True
                                    elif trigger == "on_release" and st is False:
                                        should_trigger = True
                                    
                                    if should_trigger:
                                        for key_name in key_names:
                                            self._pulse_timers[("key", key_name)] = time.time() + (pulse_ms / 1000.0)
                                        LOG.debug("flightpanel.switch.%d changed %s->%s (trigger:%s), pulsing keys %s for %dms", 
                                                 idx, prev_st, st, trigger, key_names, pulse_ms)
                                
                                self._prev_state[state_key] = st
                            else:
                                # Direct mode: store state for later application
                                self._prev_state[state_key] = st
                                for key_name in key_names:
                                    self._prev_state[f"key:{key_name}"] = st
                    if src.startswith("flightpanel.button") and device_name == "flightpanel":
                        idx = int(src.split(".")[-1])
                        st = bool(state.get("buttons", {}).get(idx, False))
                        
                        # Get mapping mode and pulse duration
                        mode = props.get("mode", "direct")  # "direct" or "toggle"
                        pulse_ms = props.get("pulse_ms", 100)  # default 100ms pulse
                        trigger = props.get("trigger", "on_change")  # "on_press", "on_release", or "on_change"
                        
                        if tgt.startswith("button:"):
                            btn_id = int(tgt.split(":", 1)[1])
                            state_key = f"flightpanel.button.{idx}"
                            
                            if mode == "toggle":
                                # Toggle mode: pulse on state change
                                prev_st = self._prev_state.get(state_key, None)
                                LOG.debug(f"flightpanel.button.{idx} toggle check: prev_st={prev_st}, st={st}, tgt={tgt}")
                                
                                # Trigger if state changed (or if this is the first time and state is True)
                                if prev_st != st:
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
                                        LOG.debug("flightpanel.button.%d changed %s->%s (trigger:%s), pulsing button:%d for %dms", 
                                                 idx, prev_st, st, trigger, btn_id, pulse_ms)
                                
                                self._prev_state[state_key] = st
                            else:
                                # Direct mode: store state for later application
                                self._prev_state[state_key] = st
                        elif tgt.startswith("key:"):
                            # Keyboard key support for flight panel buttons
                            key_names = self._key_names_from_target(tgt)
                            state_key = f"flightpanel.button.{idx}"
                            
                            if mode == "toggle":
                                # Toggle mode: pulse on state change
                                prev_st = self._prev_state.get(state_key, None)
                                
                                # Trigger if state changed (or if this is the first time and state is True)
                                if prev_st != st:
                                    # State changed - check trigger condition
                                    should_trigger = False
                                    if trigger == "on_change":
                                        should_trigger = True
                                    elif trigger == "on_press" and st is True:
                                        should_trigger = True
                                    elif trigger == "on_release" and st is False:
                                        should_trigger = True
                                    
                                    if should_trigger:
                                        for key_name in key_names:
                                            self._pulse_timers[("key", key_name)] = time.time() + (pulse_ms / 1000.0)
                                        LOG.debug("flightpanel.button.%d changed %s->%s (trigger:%s), pulsing keys %s for %dms", 
                                                 idx, prev_st, st, trigger, key_names, pulse_ms)
                                
                                self._prev_state[state_key] = st
                            else:
                                # Direct mode: store state for later application
                                self._prev_state[state_key] = st
                                for key_name in key_names:
                                    self._prev_state[f"key:{key_name}"] = st
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
                        self._prev_state[src] = st
                        if tgt.startswith("button:"):
                            btn_id = int(tgt.split(":", 1)[1])
                            cmd.buttons[btn_id] = st
                        elif tgt.startswith("key:"):
                            for key_name in self._key_names_from_target(tgt):
                                cmd.keys[key_name] = st
                        elif tgt.startswith("led:"):
                            led_name = tgt.split(":", 1)[1]
                            cmd.leds[led_name] = st
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
                    mode = props.get("mode", "direct")
                    logic = props.get("logic", "and")  # "and" or "all_same"
                    pulse_ms = props.get("pulse_ms", 100)

                    states = []
                    for src_item in src_list:
                        st, _ = self._refresh_state_from_event(src_item, device_name, state)
                        states.append(st)

                    if not states:
                        continue

                    if logic == "all_same":
                        current_condition = all(states) or not any(states)
                    else:
                        current_condition = all(states)

                    if tgt.startswith("button:"):
                        btn_id = int(tgt.split(":", 1)[1])
                        multi_state_key = f"multi:{tgt}"

                        if mode == "toggle":
                            prev_condition = self._prev_state.get(multi_state_key, False)
                            if prev_condition != current_condition and current_condition:
                                self._pulse_timers[btn_id] = time.time() + (pulse_ms / 1000.0)
                                LOG.debug("multi-input %s toggle: button:%d pulsing for %dms (states=%s)", 
                                         logic.upper(), btn_id, pulse_ms, states)
                            self._prev_state[multi_state_key] = current_condition
                        else:
                            cmd.buttons[btn_id] = current_condition
                            LOG.debug("multi-input %s direct: button:%d=%s (states=%s)", 
                                     logic.upper(), btn_id, current_condition, states)

                    if tgt.startswith("key:"):
                        key_names = self._key_names_from_target(tgt)
                        multi_state_key = f"multi:{tgt}"

                        if mode == "toggle":
                            prev_condition = self._prev_state.get(multi_state_key, False)
                            if prev_condition != current_condition and current_condition:
                                for key_name in key_names:
                                    self._pulse_timers[("key", key_name)] = time.time() + (pulse_ms / 1000.0)
                                LOG.debug("multi-input %s toggle: keys %s pulsing for %dms (states=%s)", 
                                         logic.upper(), key_names, pulse_ms, states)
                            self._prev_state[multi_state_key] = current_condition
                        else:
                            for key_name in key_names:
                                cmd.keys[key_name] = current_condition
                            LOG.debug("multi-input %s direct: keys %s=%s (states=%s)", 
                                     logic.upper(), key_names, current_condition, states)
                except Exception:
                    LOG.exception("mapping error for multi-input binding %s", b)
        
        # Check active pulse timers and apply them to the command
        # This runs on EVERY call, not just when flight panel events arrive
        current_time = time.time()
        expired_timers = []
        for timer_id, end_time in self._pulse_timers.items():
            if current_time < end_time:
                # Handle both button pulses (int) and key pulses (tuple)
                if isinstance(timer_id, tuple) and timer_id[0] == "key":
                    cmd.keys[timer_id[1]] = True
                else:
                    cmd.buttons[timer_id] = True
            else:
                expired_timers.append(timer_id)
        
        # Clean up expired timers
        for timer_id in expired_timers:
            del self._pulse_timers[timer_id]
        
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
                        st, _ = self._refresh_state_from_event(src, device_name, state)
                        cmd.buttons[btn_id] = st
                    
                    # Multiple inputs direct mode (AND logic or ALL_SAME logic)
                    elif src_list:
                        logic = props.get("logic", "and")  # "and" or "all_same"
                        
                        if logic == "all_same":
                            # Fire when ALL inputs are true OR ALL inputs are false
                            states = []
                            for src_item in src_list:
                                st, _ = self._refresh_state_from_event(src_item, device_name, state)
                                states.append(st)
                            
                            # Check if all states are the same
                            if states:
                                all_true = all(states)
                                all_false = not any(states)
                                cmd.buttons[btn_id] = all_true or all_false
                                LOG.debug("multi-input ALL_SAME condition for button:%d = %s (all_true=%s, all_false=%s)", 
                                         btn_id, all_true or all_false, all_true, all_false)
                            else:
                                cmd.buttons[btn_id] = False
                        else:
                            # Default AND logic
                            all_true = True
                            for src_item in src_list:
                                st, _ = self._refresh_state_from_event(src_item, device_name, state)
                                if not st:
                                    all_true = False
                                    break
                            cmd.buttons[btn_id] = all_true
                            LOG.debug("multi-input AND condition for button:%d = %s", btn_id, all_true)
            
            # Handle keyboard keys in direct mode
            elif tgt and tgt.startswith("key:"):
                mode = props.get("mode", "direct")
                if mode == "direct":
                    key_names = self._key_names_from_target(tgt)
                    
                    # Single input direct mode
                    if src and not b.get("inputs"):
                        st, _ = self._refresh_state_from_event(src, device_name, state)
                        for key_name in key_names:
                            cmd.keys[key_name] = st
                    
                    # Multiple inputs direct mode (AND logic or ALL_SAME logic)
                    elif src_list:
                        logic = props.get("logic", "and")  # "and" or "all_same"
                        
                        if logic == "all_same":
                            # Fire when ALL inputs are true OR ALL inputs are false
                            states = []
                            for src_item in src_list:
                                st, _ = self._refresh_state_from_event(src_item, device_name, state)
                                states.append(st)
                            
                            # Check if all states are the same
                            if states:
                                all_true = all(states)
                                all_false = not any(states)
                                for key_name in key_names:
                                    cmd.keys[key_name] = all_true or all_false
                                LOG.debug("multi-input ALL_SAME condition for keys %s = %s (all_true=%s, all_false=%s)", 
                                         key_names, all_true or all_false, all_true, all_false)
                            else:
                                for key_name in key_names:
                                    cmd.keys[key_name] = False
                        else:
                            # Default AND logic
                            all_true = True
                            for src_item in src_list:
                                st, _ = self._refresh_state_from_event(src_item, device_name, state)
                                if not st:
                                    all_true = False
                                    break
                            for key_name in key_names:
                                cmd.keys[key_name] = all_true
                            LOG.debug("multi-input AND condition for keys %s = %s", key_names, all_true)
        
        # Handle LED outputs
        for b in bindings:
            src = b.get("input")
            src_list = b.get("inputs", [src] if src else [])
            tgt = b.get("target")
            props = b.get("props", {})
            
            if tgt and tgt.startswith("led:"):
                led_name = tgt.split(":", 1)[1]
                mode = props.get("mode", "direct")
                
                # Single input direct mode
                if src and not b.get("inputs"):
                    st, _ = self._refresh_state_from_event(src, device_name, state)
                    cmd.leds[led_name] = st
                
                # Multiple inputs direct mode (AND logic or ALL_SAME logic)
                elif src_list:
                    logic = props.get("logic", "and")
                    
                    if logic == "all_same":
                        states = []
                        for src_item in src_list:
                            st, _ = self._refresh_state_from_event(src_item, device_name, state)
                            states.append(st)
                        
                        if states:
                            all_true = all(states)
                            all_false = not any(states)
                            cmd.leds[led_name] = all_true or all_false
                            LOG.debug("multi-input ALL_SAME condition for led:%s = %s", led_name, all_true or all_false)
                        else:
                            cmd.leds[led_name] = False
                    else:
                        # Default AND logic
                        all_true = True
                        for src_item in src_list:
                            st, _ = self._refresh_state_from_event(src_item, device_name, state)
                            if not st:
                                all_true = False
                                break
                        cmd.leds[led_name] = all_true
                        LOG.debug("multi-input AND condition for led:%s = %s", led_name, all_true)
        
        LOG.debug("mapped state -> %s", cmd)
        return cmd

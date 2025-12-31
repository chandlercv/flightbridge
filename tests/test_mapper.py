import pytest
from mapper import Mapper


def test_axis_invert_and_scale(tmp_path):
    profile = {
        "bindings": [
            {"input": "x55.axes.0", "target": "axis:AXIS_X", "props": {"invert": True, "scale": 0.5}},
            {"input": "x55.button.0", "target": "button:1"}
        ]
    }
    m = Mapper(profile)
    state = {"device": "x55", "axes": {0: 1.0}, "buttons": {0: True}}
    cmd = m.map_state_to_vjoy(state)

    assert pytest.approx(cmd.axes["AXIS_X"], rel=1e-3) == -0.5
    assert cmd.buttons[1] is True

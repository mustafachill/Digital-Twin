# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Nothing is defaulted: a node without its facts refuses to configure.

Each node is constructed in this process with a chosen set of parameter
overrides and driven through `configure` by calling its transition directly —
no executor, no graph — so the refusal is asserted as the lifecycle's own
answer rather than read off a log.
"""

from __future__ import annotations

from cite_hardware.deadman import Deadman, SPECS as DEADMAN_SPECS
from cite_hardware.gripper_relay import GripperRelay, SPECS as RELAY_SPECS
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.track_adapter import SPECS as TRACK_SPECS, TrackAdapter
import pytest
import rclpy
from rclpy.lifecycle import TransitionCallbackReturn
from rclpy.parameter import Parameter

GOOD = {
    "track_adapter": {
        "command_topic": "/t/cmd",
        "joint": "track_joint",
        "joint_state_topic": "/t/joint_states",
        "position_scale": 1000.0,
        "position_min_m": 0.0,
        "position_max_m": 0.7,
        "max_speed_mps": 1.0,
        "poll_period_s": 0.1,
        "auto_enable": False,
        "set_position_service": "/v/set_linear_motor_pos",
        "get_position_service": "/v/get_linear_motor_pos",
        "stop_service": "/v/set_linear_motor_stop",
        "deadman_state_topic": "/t/deadman",
    },
    "gripper_relay": {
        "action_name": "/t/gripper_cmd",
        "vendor_action_name": "/v/gripper_action",
        "open_position": 0.0,
        "closed_position": 0.85,
        "vendor_open_position": 0.0,
        "vendor_closed_position": 0.85,
        "result_timeout_s": 5.0,
        "deadman_state_topic": "/t/deadman",
        "drive_joint": "drive_joint",
        "joint_state_topic": "/t/joint_states",
        "get_position_service": "/v/get_gripper_position",
        "vendor_state_open_position": 850.0,
        "vendor_state_closed_position": 0.0,
        "poll_period_s": 0.1,
    },
    "deadman": {
        "zone": "cell_b",
        "asset_id": "picker",
        "timeout_s": 0.5,
        "state_topic": "/t/deadman",
        "set_state_service": "/v/set_state",
        "linear_motor_stop_service": "/v/set_linear_motor_stop",
        "cancel_actions": ["/t/gripper_cmd"],
        "stop_trajectory_topics": ["/t/joint_trajectory"],
    },
}

NODES = {
    "track_adapter": (TrackAdapter, TRACK_SPECS),
    "gripper_relay": (GripperRelay, RELAY_SPECS),
    "deadman": (Deadman, DEADMAN_SPECS),
}


@pytest.fixture(scope="module", autouse=True)
def _context():
    rclpy.init()
    yield
    rclpy.shutdown()


def _configure(name: str, values: dict) -> TransitionCallbackReturn:
    node_type, _specs = NODES[name]
    overrides = [Parameter(key, value=value) for key, value in values.items()]
    node = node_type(parameter_overrides=overrides)
    try:
        return node.on_configure(None)
    finally:
        node.destroy_node()


@pytest.mark.parametrize("name", sorted(NODES))
def test_every_fact_supplied_configures(name) -> None:
    assert _configure(name, GOOD[name]) == TransitionCallbackReturn.SUCCESS


@pytest.mark.parametrize(
    "name, missing",
    [(name, spec.name) for name, (_type, specs) in sorted(NODES.items()) for spec in specs],
)
def test_any_one_fact_missing_refuses(name, missing) -> None:
    values = {key: value for key, value in GOOD[name].items() if key != missing}
    assert _configure(name, values) == TransitionCallbackReturn.FAILURE


def test_the_refusal_names_every_missing_fact() -> None:
    rclpy_node = rclpy.create_node("required_parameters_probe")
    try:
        required = RequiredParameters(
            rclpy_node,
            (
                Spec("first", Parameter.Type.STRING, "the first fact"),
                Spec("second", Parameter.Type.DOUBLE, "the second fact", positive=True),
            ),
        )
        with pytest.raises(ParameterError) as error:
            required.read()
        assert "first" in str(error.value)
        assert "second" in str(error.value)
    finally:
        rclpy_node.destroy_node()


@pytest.mark.parametrize(
    "name, key, value",
    [
        ("track_adapter", "position_scale", 0.0),
        ("track_adapter", "position_max_m", -1.0),  # below position_min_m
        ("track_adapter", "joint", ""),
        ("gripper_relay", "closed_position", 0.0),  # an empty drive range
        ("gripper_relay", "vendor_action_name", "/t/gripper_cmd"),  # serving itself
        ("deadman", "timeout_s", 0.0),
        ("deadman", "cancel_actions", ["/t/gripper_cmd", ""]),
    ],
)
def test_an_unusable_fact_refuses(name, key, value) -> None:
    values = dict(GOOD[name])
    values[key] = value
    assert _configure(name, values) == TransitionCallbackReturn.FAILURE


def test_a_wrongly_typed_fact_refuses_at_configure_not_at_construction() -> None:
    values = dict(GOOD["track_adapter"])
    values["position_scale"] = "a thousand"
    assert _configure("track_adapter", values) == TransitionCallbackReturn.FAILURE


def test_the_deadman_refuses_simulated_time() -> None:
    values = dict(GOOD["deadman"])
    values["use_sim_time"] = True
    assert _configure("deadman", values) == TransitionCallbackReturn.FAILURE

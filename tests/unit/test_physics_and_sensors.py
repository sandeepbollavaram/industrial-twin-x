import numpy as np
import pytest

from modules.edge_computing.policy import EdgePolicy
from simulation.actuators.limits import validate_command
from simulation.engine.core import FactorySimulation
from simulation.factory.layout import SensorSpec
from simulation.scenarios.catalog import build_scenario
from simulation.sensors.models import Sensor


def run(scenario=None, until=3000.0, edge=False):
    sim = FactorySimulation(seed=3, scenarios=[scenario] if scenario else [], edge_enabled=edge)
    sim.run(until)
    return sim


def test_bearing_wear_raises_vibration_and_ends_in_failure():
    sim = run(build_scenario("bearing_degradation"), until=2400)
    machine = sim.machines["MTR-A01"]
    healthy = sim.machines["MTR-A02"]
    assert machine.vibration() > 2 * healthy.vibration()
    assert machine.bearing_temp > healthy.bearing_temp + 10
    sim.run(3600)
    assert machine.failed and machine.failure_reason == "bearing_seizure"


def test_overheating_without_protection_fails_and_edge_prevents_it():
    assert run(build_scenario("motor_overheating"), 3600).machines["MTR-A02"].failed
    protected = run(build_scenario("motor_overheating"), 3600, edge=True)
    machine = protected.machines["MTR-A02"]
    assert not machine.failed
    assert machine.speed_cmd == pytest.approx(0.6)
    assert machine.winding_temp < 105


def test_edge_stops_a_worn_bearing_before_seizure():
    sim = run(build_scenario("bearing_degradation"), 3600, edge=True)
    machine = sim.machines["MTR-A01"]
    assert not machine.failed
    assert machine.status == "stopped"


def test_leak_lowers_pressure_and_delivered_flow():
    sim = run(build_scenario("pump_leakage"), 1500)
    leaking, healthy = sim.machines["PMP-B01"], sim.machines["PMP-B02"]
    assert leaking.pressure() < 0.8 * healthy.pressure()
    assert leaking.delivered_flow < healthy.delivered_flow
    assert leaking.suction_flow > healthy.suction_flow


def test_power_is_conserved_through_distribution():
    sim = run(until=120)
    unit = sim.machines["PDU-C01"]
    loads = sum(m.power_kw for m in unit.loads)
    assert unit.power_kw == pytest.approx(unit.base_kw + loads, rel=0.01)


def test_tank_settles_near_its_setpoint():
    sim = run(until=3600)
    assert sim.machines["TNK-B03"].level_pct == pytest.approx(60, abs=5)


def test_sensor_noise_statistics_and_resolution():
    spec = SensorSpec("d.vibration_mm_s", "d", "vibration_mm_s")
    sensor = Sensor(spec, np.random.default_rng(0))
    values = np.array([sensor.read(2.0) for _ in range(5000)])
    assert values.mean() == pytest.approx(2.0, abs=0.05)
    assert values.std() == pytest.approx(0.05, rel=0.1)


def test_sensor_clips_to_physical_range():
    sensor = Sensor(SensorSpec("d.rpm", "d", "rpm"), np.random.default_rng(0))
    assert all(sensor.read(0.0) >= 0.0 for _ in range(200))


def test_sensor_freeze_repeats_value():
    sensor = Sensor(SensorSpec("d.rpm", "d", "rpm"), np.random.default_rng(0))
    sensor.freeze_requested = True
    assert len({sensor.read(1000.0) for _ in range(20)}) == 1


@pytest.mark.parametrize(
    "name,value,accepted",
    [
        ("set_speed", 0.6, True),
        ("set_speed", 1.5, False),
        ("set_speed", 0.1, False),
        ("set_speed", float("nan"), False),
        ("set_speed", None, False),
        ("stop", None, True),
        ("self_destruct", None, False),
    ],
)
def test_actuator_limits(name, value, accepted):
    assert validate_command(name, value).accepted is accepted


def test_edge_ignores_single_sensor_evidence():
    policy = EdgePolicy()
    assert policy.evaluate("M", {"winding_temp_c": 200.0}, {"winding_temp_c": 1}) == []


def test_edge_derates_once_then_trips():
    policy = EdgePolicy()
    votes = {"winding_temp_c": 4}
    assert policy.evaluate("M", {"winding_temp_c": 106.0}, votes)[0].command == "set_speed"
    assert policy.evaluate("M", {"winding_temp_c": 107.0}, votes) == []
    assert policy.evaluate("M", {"winding_temp_c": 131.0}, votes)[0].command == "stop"
    assert policy.evaluate("M", {"winding_temp_c": 132.0}, votes) == []

"""MQTT topic layout."""

ROOT = "industrial-twin-x/factory"


def telemetry(factory: str, zone: str, device: str) -> str:
    return f"{ROOT}/{factory}/zone/{zone}/device/{device}/telemetry"


def status(factory: str, device: str) -> str:
    return f"{ROOT}/{factory}/device/{device}/status"


def commands(factory: str, device: str) -> str:
    return f"{ROOT}/{factory}/device/{device}/commands"


def alerts(factory: str) -> str:
    return f"{ROOT}/{factory}/alerts"


def control(factory: str) -> str:
    return f"{ROOT}/{factory}/control"


def network(factory: str) -> str:
    return f"{ROOT}/{factory}/network"

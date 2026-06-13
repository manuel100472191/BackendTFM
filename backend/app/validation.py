from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class ValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Telemetry:
    node_id: str
    gateway_id: str
    timestamp: datetime
    fields: dict[str, float | int | str | bool]
    tags: dict[str, str]


RANGES: dict[str, tuple[float | None, float | None]] = {
    "temperature_c": (-40.0, 85.0),
    "humidity_pct": (0.0, 100.0),
    "pressure_hpa": (300.0, 1100.0),
    "storage_voltage_v": (0.0, 6.0),
    "soc_pct": (0.0, 100.0),
    "discharge_rate_ma": (0.0, 5000.0),
    "tx_count": (0.0, None),
    "rssi_dbm": (-160.0, 0.0),
    "snr_db": (-30.0, 30.0),
    "packet_counter": (0.0, None),
    "anomaly_score": (0.0, 1.0),
}

OPTIONAL_SECTIONS = ("weather", "energy", "communication", "tinyml")
SECTION_FIELDS = {
    "weather": ("temperature_c", "humidity_pct", "pressure_hpa"),
    "energy": ("storage_voltage_v", "soc_pct", "discharge_rate_ma", "tx_count"),
    "communication": ("rssi_dbm", "snr_db", "packet_counter"),
    "tinyml": ("anomaly_score",),
}


def parse_telemetry(payload: dict[str, Any], topic: str = "") -> Telemetry:
    errors: list[str] = []
    node_id = _required_text(payload, "node_id", errors)
    gateway_id = _text(payload.get("gateway_id")) or _gateway_from_topic(topic) or "unknown"
    timestamp = _parse_timestamp(payload.get("timestamp"), errors)

    fields: dict[str, float | int | str | bool] = {}
    for section in OPTIONAL_SECTIONS:
        value = payload.get(section)
        if value is None:
            continue
        if not isinstance(value, dict):
            errors.append(f"{section} must be an object")
            continue

        allowed = set(SECTION_FIELDS[section])
        for key, raw_value in value.items():
            if key == "strategy" and section == "tinyml":
                strategy = _text(raw_value)
                if strategy:
                    fields["tinyml_strategy"] = strategy
                else:
                    errors.append("tinyml.strategy must be a non-empty string")
                continue

            if key not in allowed:
                errors.append(f"{section}.{key} is not supported")
                continue

            number = _number(raw_value)
            if number is None:
                errors.append(f"{section}.{key} must be numeric")
                continue
            _validate_range(key, number, errors)
            fields[key] = int(number) if key in {"tx_count", "packet_counter"} else number

    if not fields:
        errors.append("at least one telemetry field is required")

    if errors:
        raise ValidationError(errors)

    return Telemetry(
        node_id=node_id,
        gateway_id=gateway_id,
        timestamp=timestamp,
        fields=fields,
        tags={"node_id": node_id, "gateway_id": gateway_id},
    )


def _required_text(payload: dict[str, Any], key: str, errors: list[str]) -> str:
    value = _text(payload.get(key))
    if not value:
        errors.append(f"{key} is required")
        return "unknown"
    return value


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _validate_range(key: str, value: float, errors: list[str]) -> None:
    min_value, max_value = RANGES[key]
    if min_value is not None and value < min_value:
        errors.append(f"{key}={value:g} is below {min_value:g}")
    if max_value is not None and value > max_value:
        errors.append(f"{key}={value:g} is above {max_value:g}")


def _parse_timestamp(value: Any, errors: list[str]) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value), UTC)
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            errors.append("timestamp must be ISO-8601 or Unix seconds")
            return datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    errors.append("timestamp must be ISO-8601 or Unix seconds")
    return datetime.now(UTC)


def _gateway_from_topic(topic: str) -> str | None:
    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "tfm" and parts[1] == "gateway":
        return parts[2] or None
    return None

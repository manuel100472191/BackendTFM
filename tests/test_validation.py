from datetime import UTC

import pytest

from backend.app.validation import ValidationError, parse_telemetry


def test_parse_valid_gateway_telemetry():
    telemetry = parse_telemetry(
        {
            "node_id": "node-01",
            "timestamp": "2026-06-13T10:00:00Z",
            "weather": {
                "temperature_c": 24.5,
                "humidity_pct": 63.0,
                "pressure_hpa": 1012.4,
            },
            "energy": {
                "storage_voltage_v": 4.1,
                "soc_pct": 82.0,
                "discharge_rate_ma": 17.5,
                "tx_count": 120,
            },
            "communication": {
                "rssi_dbm": -92,
                "snr_db": 8.5,
                "packet_counter": 774,
            },
            "tinyml": {
                "strategy": "adaptive",
                "anomaly_score": 0.12,
            },
        },
        "tfm/gateway/gw-01/telemetry",
    )

    assert telemetry.node_id == "node-01"
    assert telemetry.gateway_id == "gw-01"
    assert telemetry.timestamp.tzinfo == UTC
    assert telemetry.fields["temperature_c"] == 24.5
    assert telemetry.fields["tx_count"] == 120
    assert telemetry.fields["tinyml_strategy"] == "adaptive"


def test_rejects_out_of_range_values():
    with pytest.raises(ValidationError) as exc:
        parse_telemetry(
            {
                "node_id": "node-01",
                "weather": {"humidity_pct": 140},
                "communication": {"rssi_dbm": -200},
            }
        )

    assert "humidity_pct=140 is above 100" in exc.value.errors
    assert "rssi_dbm=-200 is below -160" in exc.value.errors


def test_requires_at_least_one_measurement():
    with pytest.raises(ValidationError) as exc:
        parse_telemetry({"node_id": "node-01"})

    assert "at least one telemetry field is required" in exc.value.errors

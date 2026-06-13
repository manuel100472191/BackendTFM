from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
import os
import random
import time


SECONDS_PER_DAY = 24 * 60 * 60


@dataclass
class NodeState:
    node_id: str
    rng: random.Random
    packet_counter: int = 0
    tx_count: int = 0
    storage_voltage_v: float = 4.1
    soc_pct: float = 95.0
    phase_shift_seconds: float = 0.0
    temperature_offset: float = 0.0
    link_offset: float = 0.0


def main() -> None:
    import paho.mqtt.client as mqtt

    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    gateway_id = os.getenv("SIM_GATEWAY_ID", "gw-01")
    node_count = int(os.getenv("SIM_NODE_COUNT", "3"))
    interval_seconds = float(os.getenv("SIM_INTERVAL_SECONDS", "5"))
    seed = int(os.getenv("SIM_SEED", "42"))
    time_acceleration = float(os.getenv("SIM_TIME_ACCELERATION", "60"))
    anomaly_rate = float(os.getenv("SIM_ANOMALY_RATE", "0.03"))

    nodes = _build_nodes(node_count=node_count, seed=seed)
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(host, port, keepalive=60)
    client.loop_start()

    started_at = time.time()
    print(
        "edge simulator started "
        f"nodes={node_count} interval={interval_seconds}s seed={seed} "
        f"time_acceleration={time_acceleration} anomaly_rate={anomaly_rate}",
        flush=True,
    )

    while True:
        simulated_elapsed = (time.time() - started_at) * time_acceleration
        for node in nodes:
            payload = _next_payload(
                node=node,
                gateway_id=gateway_id,
                simulated_elapsed=simulated_elapsed,
                anomaly_rate=anomaly_rate,
            )
            topic = f"tfm/gateway/{gateway_id}/telemetry"
            client.publish(topic, json.dumps(payload), qos=1)
            print(
                f"published node={node.node_id} packet={node.packet_counter} "
                f"temp={payload['weather']['temperature_c']}C "
                f"soc={payload['energy']['soc_pct']}% "
                f"rssi={payload['communication']['rssi_dbm']}dBm",
                flush=True,
            )
        time.sleep(interval_seconds)


def _build_nodes(*, node_count: int, seed: int) -> list[NodeState]:
    fleet_rng = random.Random(seed)
    nodes = []
    for index in range(1, node_count + 1):
        node_seed = fleet_rng.randint(1, 999_999_999)
        rng = random.Random(node_seed)
        nodes.append(
            NodeState(
                node_id=f"node-{index:02d}",
                rng=rng,
                storage_voltage_v=rng.uniform(3.9, 4.2),
                soc_pct=rng.uniform(75.0, 98.0),
                phase_shift_seconds=rng.uniform(0, SECONDS_PER_DAY),
                temperature_offset=rng.uniform(-2.0, 2.0),
                link_offset=rng.uniform(-8.0, 8.0),
            )
        )
    return nodes


def _next_payload(
    *,
    node: NodeState,
    gateway_id: str,
    simulated_elapsed: float,
    anomaly_rate: float,
) -> dict[str, object]:
    node.packet_counter += 1
    node.tx_count += 1

    day_phase = 2 * math.pi * ((simulated_elapsed + node.phase_shift_seconds) % SECONDS_PER_DAY) / SECONDS_PER_DAY
    daylight = max(0.0, math.sin(day_phase - math.pi / 2))
    is_anomaly = node.rng.random() < anomaly_rate

    temperature_c = 22.0 + node.temperature_offset + 7.0 * math.sin(day_phase - math.pi / 3)
    temperature_c += node.rng.gauss(0.0, 0.45)
    humidity_pct = 62.0 - 18.0 * math.sin(day_phase - math.pi / 3) + node.rng.gauss(0.0, 2.5)
    pressure_hpa = 1013.0 + 5.0 * math.cos(day_phase / 2) + node.rng.gauss(0.0, 0.8)

    discharge_ma = 10.0 + 20.0 * (1.0 - daylight) + node.rng.gauss(0.0, 1.5)
    charge_effect = 0.018 * daylight
    discharge_effect = 0.006 + 0.004 * (1.0 - daylight)
    node.soc_pct = _clamp(node.soc_pct + charge_effect - discharge_effect + node.rng.gauss(0.0, 0.08), 0.0, 100.0)
    node.storage_voltage_v = _clamp(3.25 + (node.soc_pct / 100.0) * 0.95 + node.rng.gauss(0.0, 0.015), 0.0, 6.0)

    rssi_dbm = -98.0 + node.link_offset + 5.0 * math.sin(day_phase / 3) + node.rng.gauss(0.0, 2.2)
    snr_db = 7.0 + (rssi_dbm + 100.0) / 10.0 + node.rng.gauss(0.0, 0.8)
    anomaly_score = _anomaly_score(
        is_anomaly=is_anomaly,
        storage_voltage_v=node.storage_voltage_v,
        rssi_dbm=rssi_dbm,
        rng=node.rng,
    )

    if is_anomaly:
        temperature_c += node.rng.choice([-1, 1]) * node.rng.uniform(6.0, 12.0)
        rssi_dbm -= node.rng.uniform(10.0, 25.0)

    return {
        "node_id": node.node_id,
        "gateway_id": gateway_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "weather": {
            "temperature_c": round(_clamp(temperature_c, -40.0, 85.0), 2),
            "humidity_pct": round(_clamp(humidity_pct, 0.0, 100.0), 2),
            "pressure_hpa": round(_clamp(pressure_hpa, 300.0, 1100.0), 2),
        },
        "energy": {
            "storage_voltage_v": round(node.storage_voltage_v, 3),
            "soc_pct": round(node.soc_pct, 2),
            "discharge_rate_ma": round(_clamp(discharge_ma, 0.0, 5000.0), 2),
            "tx_count": node.tx_count,
        },
        "communication": {
            "rssi_dbm": round(_clamp(rssi_dbm, -160.0, 0.0), 1),
            "snr_db": round(_clamp(snr_db, -30.0, 30.0), 1),
            "packet_counter": node.packet_counter,
        },
        "tinyml": {
            "strategy": "adaptive",
            "anomaly_score": round(anomaly_score, 3),
        },
    }


def _anomaly_score(*, is_anomaly: bool, storage_voltage_v: float, rssi_dbm: float, rng: random.Random) -> float:
    energy_component = max(0.0, (3.55 - storage_voltage_v) / 0.5)
    link_component = max(0.0, (-115.0 - rssi_dbm) / 35.0)
    baseline = 0.08 + 0.35 * energy_component + 0.25 * link_component + rng.gauss(0.0, 0.03)
    if is_anomaly:
        baseline += rng.uniform(0.35, 0.65)
    return _clamp(baseline, 0.0, 1.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


if __name__ == "__main__":
    main()

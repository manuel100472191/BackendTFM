from __future__ import annotations

from datetime import UTC, datetime
import json
import os
import random
import time

import paho.mqtt.client as mqtt


def main() -> None:
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_SAMPLE_TOPIC", "tfm/gateway/gw-01/telemetry")
    interval = float(os.getenv("MQTT_SAMPLE_INTERVAL", "5"))
    node_id = os.getenv("NODE_ID", "node-01")

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(host, port, keepalive=60)

    packet_counter = 0
    tx_count = 0
    while True:
        packet_counter += 1
        tx_count += 1
        payload = {
            "node_id": node_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "weather": {
                "temperature_c": round(random.uniform(18.0, 32.0), 2),
                "humidity_pct": round(random.uniform(35.0, 85.0), 2),
                "pressure_hpa": round(random.uniform(995.0, 1025.0), 2),
            },
            "energy": {
                "storage_voltage_v": round(random.uniform(3.55, 4.2), 3),
                "soc_pct": round(random.uniform(45.0, 98.0), 2),
                "discharge_rate_ma": round(random.uniform(8.0, 45.0), 2),
                "tx_count": tx_count,
            },
            "communication": {
                "rssi_dbm": round(random.uniform(-118.0, -72.0), 1),
                "snr_db": round(random.uniform(1.0, 12.0), 1),
                "packet_counter": packet_counter,
            },
            "tinyml": {
                "strategy": "adaptive",
                "anomaly_score": round(random.uniform(0.0, 0.35), 3),
            },
        }
        client.publish(topic, json.dumps(payload), qos=1)
        print(f"published sample packet {packet_counter} to {topic}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()

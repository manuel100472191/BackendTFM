from __future__ import annotations

import json
import logging
import signal
from threading import Event
from typing import Any

import paho.mqtt.client as mqtt

from app.config import Settings
from app.health import start_health_server
from app.influx_writer import InfluxTelemetryWriter
from app.validation import ValidationError, parse_telemetry


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tfm-backend")


def main() -> None:
    settings = Settings()
    stop_event = Event()
    writer = InfluxTelemetryWriter(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org,
        bucket=settings.influxdb_bucket,
    )
    health_server = start_health_server(settings.health_port, writer.ready)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.mqtt_client_id,
    )

    def on_connect(
        client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code == 0:
            logger.info("Connected to MQTT broker at %s:%s", settings.mqtt_host, settings.mqtt_port)
            client.subscribe(settings.mqtt_topic)
            logger.info("Subscribed to topic %s", settings.mqtt_topic)
        else:
            logger.error("MQTT connection failed: %s", reason_code)

    def on_message(_client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        gateway_id = _gateway_from_topic(message.topic)
        try:
            decoded = message.payload.decode("utf-8")
            payload = json.loads(decoded)
            if not isinstance(payload, dict):
                raise ValidationError(["payload must be a JSON object"])
            telemetry = parse_telemetry(payload, message.topic)
            writer.write_telemetry(telemetry)
            logger.info("Stored telemetry for node=%s gateway=%s", telemetry.node_id, telemetry.gateway_id)
        except json.JSONDecodeError as exc:
            error = f"invalid JSON payload: {exc.msg}"
            logger.warning("%s on topic=%s", error, message.topic)
            writer.write_event(gateway_id=gateway_id, event_type="invalid_json", message=error)
        except ValidationError as exc:
            error = "; ".join(exc.errors)
            logger.warning("Validation failed on topic=%s: %s", message.topic, error)
            writer.write_event(gateway_id=gateway_id, event_type="validation_error", message=error)
        except Exception:
            logger.exception("Unexpected ingestion error on topic=%s", message.topic)
            writer.write_event(gateway_id=gateway_id, event_type="backend_error", message="unexpected ingestion error")

    def shutdown(_signum: int, _frame: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()

    stop_event.wait()
    logger.info("Stopping backend")
    client.loop_stop()
    client.disconnect()
    health_server.shutdown()
    writer.close()


def _gateway_from_topic(topic: str) -> str:
    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "tfm" and parts[1] == "gateway":
        return parts[2] or "unknown"
    return "unknown"


if __name__ == "__main__":
    main()

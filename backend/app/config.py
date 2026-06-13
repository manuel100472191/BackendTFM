from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_topic: str = os.getenv("MQTT_TOPIC", "tfm/gateway/+/telemetry")
    mqtt_client_id: str = os.getenv("MQTT_CLIENT_ID", "tfm-backend-ingestion")
    influxdb_url: str = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    influxdb_token: str = os.getenv("INFLUXDB_TOKEN", "change-me-super-secret-token")
    influxdb_org: str = os.getenv("INFLUXDB_ORG", "tfm")
    influxdb_bucket: str = os.getenv("INFLUXDB_BUCKET", "sensor_data")
    health_port: int = int(os.getenv("HEALTH_PORT", "8000"))

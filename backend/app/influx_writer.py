from __future__ import annotations

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from app.validation import Telemetry


class InfluxTelemetryWriter:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self._org = org
        self._bucket = bucket
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def write_telemetry(self, telemetry: Telemetry) -> None:
        point = Point("node_telemetry").time(telemetry.timestamp, WritePrecision.NS)
        for key, value in telemetry.tags.items():
            point = point.tag(key, value)
        for key, value in telemetry.fields.items():
            point = point.field(key, value)
        self._write_api.write(bucket=self._bucket, org=self._org, record=point)

    def write_event(self, *, gateway_id: str, event_type: str, message: str) -> None:
        point = (
            Point("backend_events")
            .tag("gateway_id", gateway_id)
            .tag("event_type", event_type)
            .field("message", message)
        )
        self._write_api.write(bucket=self._bucket, org=self._org, record=point)

    def ready(self) -> bool:
        return bool(self._client.ready().status == "ready")

    def close(self) -> None:
        self._client.close()

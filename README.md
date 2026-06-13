# BackendTFM

Backend containerizado para una plataforma de monitorización IoT basada en MQTT,
InfluxDB y Grafana. El sistema representa el flujo completo de datos del
prototipo: estación BME280, lógica local TinyML, transmisión LoRa, gateway MQTT,
validación backend, almacenamiento temporal en InfluxDB y visualización en
Grafana.

## Arquitectura

El entorno Docker levanta cuatro servicios:

- `mqtt`: broker Eclipse Mosquitto para recibir mensajes publicados por el
  gateway.
- `backend`: servicio Python de ingesta que escucha MQTT, valida los mensajes,
  normaliza campos y escribe puntos en InfluxDB.
- `influxdb`: base de datos de series temporales para variables meteorológicas,
  energéticas, comunicación LoRa y eventos del backend.
- `grafana`: dashboard provisionado automáticamente para consultar estado actual
  e histórico del nodo.

## Puesta En Marcha

1. Copia el fichero de entorno:

   ```bash
   cp .env.example .env
   ```

2. Arranca la plataforma:

   ```bash
   docker compose up --build
   ```

3. Abre los servicios:

   - Backend healthcheck: <http://localhost:8000/ready>
   - InfluxDB: <http://localhost:8086>
   - Grafana: <http://localhost:3000>

Por defecto, Grafana usa `admin/admin`. Para un entorno no local, cambia las
credenciales y el token de InfluxDB en `.env`.

## Publicar Datos De Prueba

Con la plataforma levantada, puedes publicar mensajes simulados desde el
contenedor backend:

```bash
docker compose exec backend python -m app.publish_sample
```

Para simular una pequeña flota de nodos de borde de forma continua, usa el
compose adicional:

```bash
docker compose -f docker-compose.yml -f docker-compose.simulator.yml up --build
```

El servicio `edge-simulator` publica telemetría MQTT periódica con patrones
temporales deterministas: ciclos senoidales diarios para temperatura, humedad y
presión, ruido gaussiano, evolución gradual del estado energético, variaciones
en la calidad del enlace LoRa y aparición ocasional de anomalías.

Puedes ajustar el comportamiento desde `docker-compose.simulator.yml`:

- `SIM_NODE_COUNT`: número de nodos simulados.
- `SIM_INTERVAL_SECONDS`: intervalo real entre publicaciones.
- `SIM_SEED`: semilla para obtener datos reproducibles.
- `SIM_TIME_ACCELERATION`: aceleración del tiempo simulado.
- `SIM_ANOMALY_RATE`: probabilidad de anomalía por muestra.

También puedes enviar un único mensaje con `mosquitto_pub` si lo tienes
instalado localmente:

```bash
mosquitto_pub -h localhost -p 1883 -t tfm/gateway/gw-01/telemetry -m '{
  "node_id": "node-01",
  "timestamp": "2026-06-13T10:00:00Z",
  "weather": {
    "temperature_c": 24.5,
    "humidity_pct": 63.0,
    "pressure_hpa": 1012.4
  },
  "energy": {
    "storage_voltage_v": 4.1,
    "soc_pct": 82.0,
    "discharge_rate_ma": 17.5,
    "tx_count": 120
  },
  "communication": {
    "rssi_dbm": -92,
    "snr_db": 8.5,
    "packet_counter": 774
  },
  "tinyml": {
    "strategy": "adaptive",
    "anomaly_score": 0.12
  }
}'
```

## Contrato MQTT

Topic por defecto:

```text
tfm/gateway/+/telemetry
```

Payload esperado:

```json
{
  "node_id": "node-01",
  "gateway_id": "gw-01",
  "timestamp": "2026-06-13T10:00:00Z",
  "weather": {
    "temperature_c": 24.5,
    "humidity_pct": 63.0,
    "pressure_hpa": 1012.4
  },
  "energy": {
    "storage_voltage_v": 4.1,
    "soc_pct": 82.0,
    "discharge_rate_ma": 17.5,
    "tx_count": 120
  },
  "communication": {
    "rssi_dbm": -92,
    "snr_db": 8.5,
    "packet_counter": 774
  },
  "tinyml": {
    "strategy": "adaptive",
    "anomaly_score": 0.12
  }
}
```

`gateway_id` es opcional si el topic sigue el patrón
`tfm/gateway/<gateway_id>/telemetry`.

## Validación

El backend rechaza mensajes JSON inválidos, mensajes sin `node_id`, payloads sin
medidas y valores fuera de rangos coherentes:

- Temperatura: `-40..85` grados Celsius.
- Humedad relativa: `0..100` por ciento.
- Presión: `300..1100` hPa.
- Tensión de almacenamiento: `0..6` V.
- Estado de carga: `0..100` por ciento.
- Descarga: `0..5000` mA.
- RSSI: `-160..0` dBm.
- SNR: `-30..30` dB.
- Puntuación de anomalía TinyML: `0..1`.

Los mensajes válidos se almacenan en la medición `node_telemetry`. Los errores
de JSON, validación o ingesta se registran en la medición `backend_events`.

## Dashboard

Grafana provisiona automáticamente el dashboard
`TFM Environmental Node Monitoring`, con paneles para:

- Última comunicación recibida.
- Número de paquetes registrados.
- Calidad del enlace LoRa.
- Variables meteorológicas: temperatura, humedad relativa y presión.
- Comportamiento energético: tensión, estado de carga, descarga y transmisiones.
- Puntuación de anomalías asociada a TinyML.
- Eventos de backend derivados de mensajes inválidos o anomalías de ingesta.

## Desarrollo

Instala dependencias de test en local:

```bash
python -m pip install -r backend/requirements.txt -r requirements-dev.txt
```

Ejecuta las pruebas:

```bash
pytest
```

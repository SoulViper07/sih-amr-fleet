"""FastAPI server with WebSocket and MQTT bridge for real-time AMR fleet monitoring."""

import asyncio
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AMR Fleet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BROKER = "localhost"
PORT = 1883

active_websockets: list[WebSocket] = []
mqtt_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
mqtt_client: mqtt.Client | None = None


def on_mqtt_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """MQTT message callback - pushes to async queue for WebSocket broadcast."""
    try:
        payload = json.loads(msg.payload.decode())
        payload["topic"] = msg.topic
        mqtt_queue.put_nowait(payload)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode MQTT message: {e}")
    except asyncio.QueueFull:
        logger.warning("MQTT queue full, dropping message")


async def broadcast_mqtt_to_ws() -> None:
    """Background task: reads from MQTT queue and broadcasts to all WebSocket clients."""
    while True:
        try:
            message = await mqtt_queue.get()
            if not active_websockets:
                continue

            message_str = json.dumps(message)
            disconnected: list[WebSocket] = []

            for ws in active_websockets:
                try:
                    await ws.send_text(message_str)
                except Exception:
                    disconnected.append(ws)

            for ws in disconnected:
                if ws in active_websockets:
                    active_websockets.remove(ws)

        except Exception as e:
            logger.error(f"Error in broadcast task: {e}")
            await asyncio.sleep(0.1)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize MQTT client and start background broadcast task."""
    global mqtt_client

    mqtt_client = mqtt.Client(client_id="fastapi-bridge", clean_session=True)
    mqtt_client.on_message = on_mqtt_message

    try:
        mqtt_client.connect(BROKER, PORT, keepalive=60)
        mqtt_client.subscribe("fleet/telemetry", qos=1)
        mqtt_client.subscribe("fleet/grid", qos=1)
        mqtt_client.loop_start()
        logger.info("MQTT client connected and subscribed")

        asyncio.create_task(broadcast_mqtt_to_ws())
        logger.info("WebSocket broadcast task started")

    except Exception as e:
        logger.error(f"Failed to start MQTT client: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup MQTT client on shutdown."""
    global mqtt_client
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client disconnected")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time fleet data."""
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info(f"WebSocket connected. Total: {len(active_websockets)}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(active_websockets)}")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "amr-fleet-api"}


class DispatchRequest(BaseModel):
    x: int
    y: int


@app.post("/api/dispatch/{agent_id}")
async def dispatch_agent(agent_id: str, request: DispatchRequest) -> dict[str, Any]:
    """Dispatch an agent to a new target coordinate."""
    global mqtt_client
    if not mqtt_client:
        raise HTTPException(status_code=503, detail="MQTT client not initialized")

    payload = {"x": request.x, "y": request.y}
    topic = f"fleet/dispatch/{agent_id}"
    mqtt_client.publish(topic, json.dumps(payload), qos=1)
    logger.info(f"Dispatched {agent_id} to ({request.x}, {request.y})")

    return {"status": "dispatched", "agent": agent_id, "target": [request.x, request.y]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
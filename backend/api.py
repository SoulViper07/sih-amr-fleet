"""FastAPI server with WebSocket and MQTT bridge for real-time AMR fleet monitoring."""

import asyncio
import json
import logging
import random
import time
import uuid
from typing import Any

import paho.mqtt.client as mqtt
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.metrics import FleetMetricsCollector, get_collector

collector = get_collector()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Warehouse Configuration
WAREHOUSE_CONFIG = {
    "grid_size": [30, 30],
    "racks": {
        "rack_1": [(x, y) for x in range(4, 6) for y in range(6, 25)],
        "rack_2": [(x, y) for x in range(10, 12) for y in range(6, 25)],
        "rack_3": [(x, y) for x in range(16, 18) for y in range(6, 25)],
        "rack_4": [(x, y) for x in range(22, 24) for y in range(6, 25)],
    },
    "charging_stations": [(0, 0), (0, 29), (29, 0), (29, 29), (14, 0), (14, 29)],
    "workstations": [(2, 29), (14, 29), (27, 29)],
}

# Flatten all rack coordinates into obstacles
OBSTACLES = []
for rack_coords in WAREHOUSE_CONFIG["racks"].values():
    OBSTACLES.extend(rack_coords)

# Sabotage system
SABOTAGED_AGENTS = []

# Task system for Edge-AI bidding
PENDING_TASKS = []

app = FastAPI(title="AMR Fleet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", 1883))

active_websockets: list[WebSocket] = []
mqtt_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
mqtt_client: mqtt.Client | None = None
latest_sim_tick: int = 0
latest_fleet_state: dict[str, dict[str, Any]] = {}


def on_mqtt_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """MQTT message callback - pushes to async queue for WebSocket broadcast."""
    global latest_sim_tick
    print(f"MQTT IN: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        payload["topic"] = msg.topic
        if "time" in payload and isinstance(payload["time"], (int, float)) and payload["time"] < 1_000_000_000:
            latest_sim_tick = int(payload["time"])
        if payload.get("agent_id"):
            aid = payload["agent_id"]
            if aid not in latest_fleet_state:
                latest_fleet_state[aid] = {}
            latest_fleet_state[aid].update(payload)
        if msg.topic == "fleet/metrics":
            collector.update_from_snapshot(payload)
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

            # Include live metrics summary under "metrics" key
            message["metrics"] = collector.get_snapshot()

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
    global mqtt_client, SABOTAGED_AGENTS, PENDING_TASKS
    SABOTAGED_AGENTS.clear()
    PENDING_TASKS.clear()

    mqtt_client = mqtt.Client(client_id=f"fastapi_bridge_{uuid.uuid4().hex[:8]}", clean_session=True)
    mqtt_client.on_message = on_mqtt_message

    try:
        mqtt_client.connect(BROKER, PORT, keepalive=60)
        mqtt_client.subscribe("fleet/telemetry", qos=1)
        mqtt_client.subscribe("fleet/grid", qos=1)
        mqtt_client.subscribe("fleet/metrics", qos=1)
        mqtt_client.subscribe("amr/+/heartbeat", qos=1)
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


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Return grid configuration."""
    return {
        "grid_size": WAREHOUSE_CONFIG["grid_size"],
        "obstacles": OBSTACLES,
        "charging_stations": WAREHOUSE_CONFIG["charging_stations"],
        "warehouse": WAREHOUSE_CONFIG,
    }


@app.get("/api/sabotage/status")
async def get_sabotage_status() -> dict[str, Any]:
    """Return list of sabotaged agents."""
    return {"sabotaged": SABOTAGED_AGENTS}


@app.post("/api/sabotage/{agent_id}")
async def sabotage_agent(agent_id: str) -> dict[str, Any]:
    """Sabotage an agent (mark as dead)."""
    global mqtt_client, latest_fleet_state
    if agent_id not in SABOTAGED_AGENTS:
        SABOTAGED_AGENTS.append(agent_id)
        logger.info(f"Agent {agent_id} sabotaged!")

    # Retrieve agent's last known battery level and position from in-memory fleet state cache
    agent_state = latest_fleet_state.get(agent_id, {})
    last_battery = agent_state.get("battery", 0.0)
    latest_fleet_state[agent_id] = {
        **agent_state,
        "status": "DEAD",
        "battery": round(float(last_battery), 1),
    }

    if mqtt_client:
        payload = {"agent_id": agent_id, "action": "sabotage"}
        mqtt_client.publish(f"amr/{agent_id}/sabotage", json.dumps(payload), qos=1)
        mqtt_client.publish(f"fleet/sabotage/{agent_id}", json.dumps(payload), qos=1)

        telemetry_payload = {
            "agent_id": agent_id,
            "status": "DEAD",
            "time": latest_sim_tick,
            "battery": round(float(last_battery), 1),
            "x": agent_state.get("x", 0),
            "y": agent_state.get("y", 0),
        }
        mqtt_client.publish(
            "fleet/telemetry",
            json.dumps(telemetry_payload),
            qos=1,
        )
    return {"status": "success", "sabotaged": agent_id, "all_sabotaged": SABOTAGED_AGENTS}


@app.post("/api/fleet/revive")
async def revive_fleet() -> dict[str, Any]:
    """Revive all agents in the fleet."""
    global mqtt_client, SABOTAGED_AGENTS
    SABOTAGED_AGENTS.clear()
    if mqtt_client:
        payload = {"action": "revive"}
        mqtt_client.publish("amr/all/revive", json.dumps(payload), qos=1)
    logger.info("Fleet revive requested via API")
    return {"status": "success", "message": "All AMRs revived"}


class TaskRequest(BaseModel):
    x: int
    y: int


@app.post("/api/tasks")
async def create_task(request: TaskRequest) -> dict[str, Any]:
    """Create a new task for AMRs to bid on."""
    task_id = f"task_{uuid.uuid4().hex[:6]}"
    task = {
        "id": task_id,
        "x": request.x,
        "y": request.y,
        "created_at": time.time(),
        "claimed": False,
    }
    PENDING_TASKS.append(task)
    collector.record_task_created()
    rfp_msg = f"[TASK RFP] Broadcasted target @ ({request.x}, {request.y}) to fleet auction pool"
    logger.info(rfp_msg)
    if mqtt_client:
        rfp_telemetry = {
            "type": "TASK_RFP",
            "status": "RFP",
            "agent_id": "SWARM",
            "x": request.x,
            "y": request.y,
            "task_id": task_id,
            "message": rfp_msg,
            "time": latest_sim_tick,
        }
        mqtt_client.publish("fleet/telemetry", json.dumps(rfp_telemetry), qos=1)
    return {"status": "task_broadcasted", "task": task}


@app.get("/api/tasks")
async def get_tasks() -> dict[str, Any]:
    """Return all pending tasks for AMRs to bid on."""
    return {"tasks": PENDING_TASKS}


@app.get("/api/metrics")
async def get_metrics() -> dict[str, Any]:
    """Return live fleet performance and safety metrics snapshot."""
    return collector.get_snapshot()


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
    agent_id_num = agent_id.replace("AMR-", "")
    dispatch_msg = f"[WMS RFP] Injected task contract @ ({request.x}, {request.y}) -> Auction awarded to AMR-{agent_id_num}"
    logger.info(dispatch_msg)
    dispatch_telemetry = {
        "type": "DISPATCH",
        "status": "CNP",
        "agent_id": f"AMR-{agent_id_num}",
        "x": request.x,
        "y": request.y,
        "message": dispatch_msg,
        "time": latest_sim_tick,
    }
    mqtt_client.publish("fleet/telemetry", json.dumps(dispatch_telemetry), qos=1)

    return {"status": "dispatched", "agent": agent_id, "target": [request.x, request.y]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
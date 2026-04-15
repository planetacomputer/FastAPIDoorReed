from typing import Set
from fastapi import WebSocket

# Active websocket connections
ws_connections: Set[WebSocket] = set()

async def broadcast_payload(payload: dict):
    """Broadcast payload to all connected websockets, pruning dead connections."""
    dead = []
    for ws in list(ws_connections):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for d in dead:
        ws_connections.discard(d)

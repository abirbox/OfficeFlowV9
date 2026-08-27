"""In-memory WebSocket connection manager for real-time dispatch notifications."""
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id -> set of active websocket connections
        self.active: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        conns = self.active.get(user_id)
        if conns:
            conns.discard(ws)
            if not conns:
                self.active.pop(user_id, None)

    async def send_to_users(self, user_ids, message: dict):
        if not user_ids:
            return
        data = json.dumps(message, default=str)
        for uid in set(user_ids):
            for ws in list(self.active.get(uid, [])):
                try:
                    await ws.send_text(data)
                except Exception:
                    self.disconnect(uid, ws)


manager = ConnectionManager()

class ConnectionManager:
    """Manages WebSocket connections per project."""

    def __init__(self):
        self.active_connections: dict[str, list] = {}

    async def connect(self, project_id: str, websocket):
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    async def disconnect(self, project_id: str, websocket):
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)

    async def broadcast(self, project_id: str, event: dict):
        if project_id in self.active_connections:
            for ws in self.active_connections[project_id]:
                await ws.send_json(event)


manager = ConnectionManager()

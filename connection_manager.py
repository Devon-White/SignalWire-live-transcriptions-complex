import json
from typing import List
from fastapi import WebSocket
from asyncio import TimeoutError, Queue


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.list_update: Queue = Queue()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    @staticmethod
    async def send_personal_message(message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
    async def listen_for_updates(self, call_list):  # New method to continuously listen for updates
        while True:
            try:
                update = await self.list_update.get()
                if update:
                    await self.broadcast(
                        json.dumps({'action': 'update_call_list', 'callList': list(call_list.keys())}))
            except TimeoutError:
                pass


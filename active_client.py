import asyncio
import json
from enum import Enum
from typing import Optional, Dict, Any
from fastapi import WebSocket


class ActionType(Enum):
    INPUT = 'input'
    CLOSE = 'close'


class ActiveClient:
    """Represents an active client."""

    def __init__(self, current_websocket: WebSocket, call_list, manager, db_manager):
        self.websocket = current_websocket
        self.client_queue: asyncio.Queue = asyncio.Queue()
        self.sid: Optional[str] = None
        self.task = asyncio.create_task(self.event_handler())
        self.call_list = call_list
        self.manager = manager
        self.db_manager = db_manager

    async def event_handler(self):
        """Handle events for this client."""
        while True:
            message = await self.client_queue.get()
            if message is None:
                break
            await self.websocket.send_text(json.dumps({'action': 'transcript_message', 'transcript': message}))

    async def match_handler(self, data: Dict[str, Any]):
        """Handle matching events for this client."""
        action = ActionType(data['action'])
        if action == ActionType.INPUT:
            self.sid = data["call_sid"]
            if self.sid not in self.call_list:
                await self.manager.send_personal_message(
                    json.dumps({'action': 'error', 'error_message': "Invalid SID"}),
                    self.websocket)
            else:
                self.call_list[self.sid].clients.append(self)

                # Query the database for transcript history
                transcripts = await self.db_manager.get_transcripts(self.sid)

                # Gather the history into a list of dictionaries
                history = [{'datetime': transcript[0], 'speaker': transcript[1], 'transcript': transcript[2]} for
                           transcript in transcripts]

                # Send the history to the client
                await self.manager.send_personal_message(json.dumps({
                    'action': 'history',
                    'history': history}),
                    self.websocket)

                await self.manager.send_personal_message(json.dumps({'action': 'input', 'sid': self.sid}),
                                                         self.websocket)

        elif action == ActionType.CLOSE:
            self.sid = data["call_sid"]
            if self.sid in self.call_list:
                self.call_list[self.sid].clients.remove(self)

import asyncio
import json


async def send_list_update(manager, list_update, call_list):
    """Send updates to all connected WebSocket clients."""
    while True:
        try:
            # Get the message from the list_update queue
            update = await list_update.get()
            if update:
                # Loop through all connected WebSocket clients and send the update to each client
                await manager.broadcast(json.dumps({'action': 'update_call_list', 'callList': list(call_list.keys())}))
        except asyncio.TimeoutError:
            pass

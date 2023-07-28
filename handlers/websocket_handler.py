import base64
import json
from pydub import AudioSegment
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from active_call import ActiveCall
from active_client import ActiveClient
from config import manager, call_list, settings, db_manager, dg_client

router = APIRouter()


@router.websocket('/listen')
async def listen(websocket: WebSocket):
    await manager.connect(websocket)
    client = ActiveClient(websocket, call_list, manager, db_manager)
    await manager.send_personal_message(json.dumps({'action': 'update_call_list', 'callList': list(call_list.keys())}),
                                        websocket)

    try:
        while True:
            ws = await websocket.receive_text()
            data = json.loads(ws)
            await client.match_handler(data)
    except WebSocketDisconnect:
        print(f'{websocket.client} WebSocket Connection closed...')
    finally:
        client.task.cancel()
        manager.disconnect(websocket)
        del client


@router.websocket('/media')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    in_buffer = bytearray()
    out_buffer = bytearray()
    buffer_size = 20 * 160
    deepgram_socket = None
    call_class = None
    try:
        while True:
            ws = await websocket.receive_text()
            data = json.loads(ws)
            if data['event'] == "connected":
                pass
            elif data['event'] == "start":
                sid = data['start']['callSid']
                call_class = ActiveCall(sid, dg_client, call_list, db_manager)
                call_list[sid] = call_class

                deepgram_socket = await call_class.connect_to_deepgram()
                await manager.list_update.put("update")

            elif data['event'] == "media":
                if deepgram_socket is not None:
                    payload = base64.b64decode(data.get('media', {}).get('payload', ''))
                    track = data.get('media', {}).get('track')

                    if track == 'inbound':
                        in_buffer.extend(payload)
                    if track == 'outbound':
                        out_buffer.extend(payload)
            elif data['event'] == "stop":
                if deepgram_socket is not None:
                    deepgram_socket.send(json.dumps({'type': 'CloseStream'}))
                    del call_list[call_class.sid]
                    await manager.list_update.put("update")
                    break

            while len(in_buffer) >= buffer_size and len(out_buffer) >= buffer_size:
                as_inbound = AudioSegment(bytes(in_buffer[:buffer_size]), sample_width=1, frame_rate=8000, channels=1)
                as_outbound = AudioSegment(bytes(out_buffer[:buffer_size]), sample_width=1, frame_rate=8000, channels=1)
                mixed = AudioSegment.from_mono_audiosegments(as_inbound, as_outbound)
                deepgram_socket.send(mixed.raw_data)

                in_buffer = in_buffer[buffer_size:]
                out_buffer = out_buffer[buffer_size:]
    except WebSocketDisconnect:
        print(f'{websocket.client} WebSocket Connection closed...')
    except Exception as error:
        print(f"Could not process audio: {error}")
    finally:
        print(call_list)
        await websocket.close(int(settings.PORT))

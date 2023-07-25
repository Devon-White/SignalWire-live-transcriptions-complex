import asyncio
import base64
import csv
import json
import os
from datetime import datetime
import uvicorn
from typing import Optional, Dict, List, Any
from deepgram import Deepgram
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, staticfiles, templating, responses
from loguru import logger
from pydub import AudioSegment
from pyngrok import ngrok
from signalwire.rest import Client as SignalwireClient
from signalwire.voice_response import VoiceResponse, Start, Stream, Dial
from enum import Enum
import sqlite3

# Load environment variables
load_dotenv()


class ActionType(Enum):
    INPUT = 'input'
    CLOSE = 'close'


class Settings:
    TO_NUMBER: str = os.getenv('TO_NUMBER')
    WEBHOOK_NUM: str = os.getenv('WEBHOOK_NUM')
    PORT: str = os.getenv('port')
    PROJECT: str = os.getenv('PROJECT')
    SW_TOKEN: str = os.getenv('SW_TOKEN')
    SPACE: str = os.getenv('SPACE')
    PUBLIC_URL: Optional[str] = None


# Set up settings
settings = Settings()

# Initialize Deepgram client
dg_client = Deepgram(os.getenv('DEEPGRAM_TOKEN'))

# Initialize Signalwire client
client = SignalwireClient(settings.PROJECT, settings.SW_TOKEN, signalwire_space_url=settings.SPACE)

# Initialize call list and other data structures
call_list: Dict[str, Any] = {}
all_clients: List[Any] = []
list_update: asyncio.Queue = asyncio.Queue()

# Set up FastAPI app and templates
app = FastAPI()
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")
templates = templating.Jinja2Templates(directory="templates")
staticfiles.StaticFiles()

# Initialize SQLite database
conn = sqlite3.connect('transcript.db')
c = conn.cursor()

# Create calls table if it does not exist
c.execute("""
    CREATE TABLE IF NOT EXISTS calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT NOT NULL
    )
""")

# Create transcripts table if it does not exist
c.execute("""
    CREATE TABLE IF NOT EXISTS transcripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datetime TEXT NOT NULL,
        speaker TEXT NOT NULL,
        transcript TEXT NOT NULL,
        call_id INTEGER,
        FOREIGN KEY(call_id) REFERENCES calls(id)
    )
""")

conn.commit()


# Connection manager class
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

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


# Initialize connection manager
manager = ConnectionManager()


async def send_list_update():
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


class ActiveCall:
    """Represents an active call."""

    def __init__(self, sid: str):
        self.sid = sid
        self.clients: List['ActiveClient'] = []

    async def get_transcript(self, data: Dict[str, Any]):
        """Get the transcript from the data and send it to the clients."""
        if 'channel' in data:
            channel_index = data['channel_index']
            speaker = 'caller' if channel_index == [0, 2] else 'callee' if channel_index == [1, 2] else 'unknown'
            transcript = data['channel']['alternatives'][0]['transcript']
            logger.info(data)
            if self.sid in call_list and transcript:
                logger.info(transcript)
                for client in call_list[self.sid].clients:
                    await client.client_queue.put(
                        {'action': 'transcript_message', 'speaker': speaker, 'transcript': transcript})

                # Insert the transcript into the transcripts table with the call_id as a foreign key
                c.execute("INSERT INTO transcripts (datetime, speaker, transcript, call_id) VALUES (?, ?, ?, ?)",
                          (datetime.now(), speaker, transcript, self.sid))
                conn.commit()  # Commit the changes to the database

    async def connect_to_deepgram(self) -> Any:
        """Connect to Deepgram."""
        try:
            socket = await dg_client.transcription.live({
                'punctuate': True,
                'encoding': "mulaw",
                'sample_rate': 8000,
                'channels': 2,
                'model': 'phonecall',
                'language': 'en-US',
                'tier': 'nova',
                'interim_results': False,
                'multichannel': True,
                'endpointing': 100,
                'numerals': True
            })
            socket.registerHandler(socket.event.CLOSE, lambda c: logger.info(f'Connection closed with code {c}.'))
            socket.registerHandler(socket.event.TRANSCRIPT_RECEIVED, self.get_transcript)

            return socket
        except Exception as error:
            raise Exception(f'Could not open socket: {error}')


class ActiveClient:
    """Represents an active client."""

    def __init__(self, current_websocket: WebSocket):
        self.websocket = current_websocket
        self.client_queue: asyncio.Queue = asyncio.Queue()
        self.sid: Optional[str] = None
        self.task = asyncio.create_task(self.event_handler())

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
            if self.sid not in call_list:
                await manager.send_personal_message(json.dumps({'action': 'error', 'error_message': "Invalid SID"}),
                                                    self.websocket)
            else:
                call_list[self.sid].clients.append(self)

                # Query the database for transcript history
                c.execute("""
                    SELECT datetime, speaker, transcript
                    FROM transcripts
                    WHERE call_id = ?
                """, (self.sid,))

                transcripts = c.fetchall()

                # Gather the history into a list of dictionaries
                history = [{'datetime': transcript[0], 'speaker': transcript[1], 'transcript': transcript[2]} for transcript in transcripts]

                # Send the history to the client
                await manager.send_personal_message(json.dumps({
                    'action': 'history',
                    'history': history}),
                    self.websocket)

                await manager.send_personal_message(json.dumps({'action': 'input', 'sid': self.sid}), self.websocket)



        elif action == ActionType.CLOSE:
            logger.info("close event")
            self.sid = data["call_sid"]
            if self.sid in call_list:
                call_list[self.sid].clients.remove(self)


@app.get('/')
async def index():
    return templates.TemplateResponse('index.html', {"request": {}})


@app.get("/download/{call_id}")
async def download_logs(call_id: str):
    # Check if call_id exists in the database
    c.execute("SELECT EXISTS(SELECT 1 FROM calls WHERE call_id=?)", (call_id,))
    if not c.fetchone()[0]:
        raise HTTPException(status_code=404, detail="Call not found")

    # Filter the database for transcripts based on the call ID
    c.execute("""
        SELECT datetime, speaker, transcript
        FROM transcripts
        WHERE call_id = ?
    """, (call_id,))

    transcripts = c.fetchall()

    # If no transcripts found, return 404 error
    if not transcripts:
        raise HTTPException(status_code=404, detail="Transcripts not found")

    # Write the results to a CSV file
    csv_file = f'./csvs/{call_id}.csv'
    with open(csv_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["datetime", "speaker", "transcript"])  # write the header
        writer.writerows(transcripts)  # write the data

    return responses.FileResponse(csv_file, media_type='text/csv', filename=f'{call_id}_transcript.csv')


@app.websocket('/listen')
async def listen(websocket: WebSocket):
    await manager.connect(websocket)
    client = ActiveClient(websocket)
    asyncio.create_task(send_list_update())
    await manager.send_personal_message(json.dumps({'action': 'update_call_list', 'callList': list(call_list.keys())}),
                                        websocket)

    try:
        while True:
            ws = await websocket.receive_text()
            data = json.loads(ws)
            await client.match_handler(data)
    except WebSocketDisconnect:
        logger.info(f'{websocket.client} WebSocket Connection closed...')
    finally:
        client.task.cancel()
        manager.disconnect(websocket)
        del client


@app.post('/inbound')
async def inbound_call():
    public_url = settings.PUBLIC_URL
    public_url = public_url.replace("https", "wss").replace("http", "wss") + '/media'
    logger.info(public_url)

    response = VoiceResponse()
    start = Start()
    stream = Stream(name='stream', url=public_url, track="both_tracks")
    start.append(stream)
    response.append(start)

    dial = Dial()
    dial.number(settings.TO_NUMBER)
    response.append(dial)

    return responses.Response(content=response.to_xml(), media_type='application/xml')


@app.websocket('/media')
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
                call_class = ActiveCall(sid)
                call_list[sid] = call_class

                # Insert the call_id into the calls table and get the rowid
                c.execute("INSERT INTO calls (call_id) VALUES (?)", (sid,))
                conn.commit()  # Commit the changes to the database

                deepgram_socket = await call_class.connect_to_deepgram()
                await list_update.put("update")

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
                    await list_update.put("update")
                    break

            while len(in_buffer) >= buffer_size and len(out_buffer) >= buffer_size:
                as_inbound = AudioSegment(bytes(in_buffer[:buffer_size]), sample_width=1, frame_rate=8000, channels=1)
                as_outbound = AudioSegment(bytes(out_buffer[:buffer_size]), sample_width=1, frame_rate=8000, channels=1)
                mixed = AudioSegment.from_mono_audiosegments(as_inbound, as_outbound)
                deepgram_socket.send(mixed.raw_data)

                in_buffer = in_buffer[buffer_size:]
                out_buffer = out_buffer[buffer_size:]
    except WebSocketDisconnect:
        logger.info(f'{websocket.client} WebSocket Connection closed...')
    except Exception as error:
        logger.error(f"Could not process audio: {error}")
    finally:
        logger.info(call_list)
        await websocket.close(int(settings.PORT))


@app.on_event("shutdown")
def shutdown_event():
    c.close()
    conn.close()


def start_ngrok():
    logger.info("Starting ngrok tunnel...")
    tunnel_url = ngrok.connect(int(settings.PORT), bind_tls=True).public_url
    settings.PUBLIC_URL = tunnel_url

    incoming_phone_numbers = client.incoming_phone_numbers.list(phone_number=settings.WEBHOOK_NUM)
    sid = incoming_phone_numbers[0].sid if incoming_phone_numbers else logger.error("Invalid Webhook number")

    client.incoming_phone_numbers(sid).update(voice_url=f"{tunnel_url}/inbound", voice_receive_mode="voice")
    logger.info(f"Signalwire Number updated...\n Public Url: {tunnel_url}")
    logger.info(f"Call {settings.WEBHOOK_NUM} to start transcribing a call...")


if __name__ == "__main__":
    try:
        start_ngrok()
    except Exception as e:
        logger.error(f"{e}")
    uvicorn.run(app=app, host='127.0.0.1', port=int(settings.PORT), log_level="info")

from typing import List, Dict, Any
from datetime import datetime
from active_client import ActiveClient


class ActiveCall:
    """Represents an active call."""

    def __init__(self, sid: str, dg_client, call_list, db_manager):
        self.sid = sid
        self.clients: List['ActiveClient'] = []
        self.dg_client = dg_client
        self.call_list = call_list
        self.db_manager = db_manager

    async def get_transcript(self, data: Dict[str, Any]):
        """Get the transcript from the data and send it to the clients."""
        if 'channel' in data:
            channel_index = data['channel_index']
            speaker = 'caller' if channel_index == [0, 2] else 'callee' if channel_index == [1, 2] else 'unknown'
            transcript = data['channel']['alternatives'][0]['transcript']
            if self.sid in self.call_list and transcript:
                for client in self.call_list[self.sid].clients:
                    await client.client_queue.put(
                        {'action': 'transcript_message', 'speaker': speaker, 'transcript': transcript})

                # Insert the transcript into the transcripts table with the call_id as a foreign key
                await self.db_manager.insert_transcript(datetime.now(), speaker, transcript, self.sid)

    async def connect_to_deepgram(self) -> Any:
        """Connect to Deepgram."""
        try:
            socket = await self.dg_client.transcription.live({
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
            socket.registerHandler(socket.event.CLOSE, lambda c: print(f'Connection closed with code {c}.'))
            socket.registerHandler(socket.event.TRANSCRIPT_RECEIVED, self.get_transcript)

            return socket
        except Exception as error:
            raise Exception(f'Could not open socket: {error}')

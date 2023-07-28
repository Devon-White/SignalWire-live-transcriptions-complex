import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from enum import Enum
from database_manager import DatabaseManager
from connection_manager import ConnectionManager
from deepgram import Deepgram
import asyncio

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

# Initialize SQLite database
db_manager = DatabaseManager('transcript.db')

# Initialize ConnectionManager
manager = ConnectionManager()

# Initialize call list and list_update
call_list: Dict[str, Any] = {}

# Initialize Deepgram client
dg_client = Deepgram(os.getenv('DEEPGRAM_TOKEN'))

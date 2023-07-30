import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class Settings:
    TO_NUMBER: str = os.getenv('TO_NUMBER')
    WEBHOOK_NUM: str = os.getenv('WEBHOOK_NUM')
    PORT: str = os.getenv('PORT', '3000')
    PROJECT: str = os.getenv('PROJECT')
    SW_TOKEN: str = os.getenv('SW_TOKEN')
    SPACE: str = os.getenv('SPACE')
    PUBLIC_URL: Optional[str] = None


# Set up settings
settings = Settings()

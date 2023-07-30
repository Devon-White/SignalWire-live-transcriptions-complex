import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, staticfiles
from pyngrok import ngrok
from signalwire.rest import Client as SignalwireClient
from config import settings, manager, call_list
from handlers import http_handler, websocket_handler
import asyncio

# Load environment variables
load_dotenv()

client = SignalwireClient(settings.PROJECT, settings.SW_TOKEN, signalwire_space_url=settings.SPACE)

app = FastAPI()
app.include_router(http_handler.router)
app.include_router(websocket_handler.router)
app.mount('/static', staticfiles.StaticFiles(directory="static"), name="static")


def start_ngrok():
    print("Starting ngrok tunnel...")
    tunnel_url = ngrok.connect(int(settings.PORT), bind_tls=True).public_url
    settings.PUBLIC_URL = tunnel_url

    incoming_phone_numbers = client.incoming_phone_numbers.list(phone_number=settings.WEBHOOK_NUM)
    sid = incoming_phone_numbers[0].sid if incoming_phone_numbers else print("Invalid Webhook number")

    client.incoming_phone_numbers(sid).update(voice_url=f"{tunnel_url}/inbound", voice_receive_mode="voice")
    print(f"Signalwire Number updated...\n Public Url: {tunnel_url}")
    print(f"Call {settings.WEBHOOK_NUM} to start transcribing a call...")


@app.on_event("startup")
async def startup_event():
    # Start the task for listening for updates when the application starts
    asyncio.create_task(manager.listen_for_updates(call_list))


if __name__ == "__main__":
    try:
        start_ngrok()
    except Exception as e:
        print(f"{e}")
    uvicorn.run(app=app, host='0.0.0.0', port=int(settings.PORT), log_level="info")

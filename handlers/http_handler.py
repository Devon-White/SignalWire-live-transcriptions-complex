import csv
from fastapi import HTTPException, responses, templating, APIRouter
from signalwire.voice_response import VoiceResponse, Start, Stream, Dial
from config import db_manager, settings

templates = templating.Jinja2Templates(directory="templates")

router = APIRouter()


@router.get('/')
async def index():
    return templates.TemplateResponse('index.html', {"request": {}})


@router.get('/download/{call_id}')
async def download_logs(call_id: str):
    # Check if call_id exists in the database
    transcripts = await db_manager.get_transcripts(call_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="Transcripts not found")

    # Write the results to a CSV file
    csv_file = f'./csvs/{call_id}.csv'
    with open(csv_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["datetime", "speaker", "transcript"])  # write the header
        writer.writerows(transcripts)  # write the data

    return responses.FileResponse(csv_file, media_type='text/csv', filename=f'{call_id}_transcript.csv')


@router.post('/inbound')
async def inbound_call():
    public_url = settings.PUBLIC_URL
    public_url = public_url.replace("https", "wss").replace("http", "wss") + '/media'
    print(public_url)

    response = VoiceResponse()
    start = Start()
    stream = Stream(name='stream', url=public_url, track="both_tracks")
    start.append(stream)
    response.append(start)

    dial = Dial()
    dial.number(settings.TO_NUMBER)
    response.append(dial)

    return responses.Response(content=response.to_xml(), media_type='application/xml')

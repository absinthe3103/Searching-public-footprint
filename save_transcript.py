import sys, os
sys.path.insert(0, 'Backend/database')
sys.path.insert(0, 'Backend/src')
from dotenv import load_dotenv
load_dotenv()
from db import get_interviews, update_interview_status

# Session from today's Vexa log
SESSION_UID = '3f239e81-9271-48b7-8391-03efc2b0476a'
# Interview ID for today's session (Vexa meeting_id=19, maps to our interview id=30)
INTERVIEW_ID = 30

import requests, tempfile
from minio import Minio

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
MINIO_ACCESS   = os.getenv('MINIO_ACCESS_KEY', 'vexa-access-key')
MINIO_SECRET   = os.getenv('MINIO_SECRET_KEY', 'vexa-secret-key')
MINIO_BUCKET   = os.getenv('MINIO_BUCKET', 'vexa')

print(f"Connecting to MinIO at {MINIO_ENDPOINT}...")
client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)

objects = list(client.list_objects(MINIO_BUCKET, recursive=True))
chunks = sorted([o for o in objects if SESSION_UID in o.object_name], key=lambda o: o.object_name)
print(f"Found {len(chunks)} chunk(s)")

combined = bytearray()
for chunk_obj in chunks:
    data = client.get_object(MINIO_BUCKET, chunk_obj.object_name)
    chunk_bytes = data.read()
    if len(chunk_bytes) > 1000:  # skip tiny final/empty chunks
        combined.extend(chunk_bytes)
        print(f"  + {chunk_obj.object_name} ({len(chunk_bytes)} bytes)")
    else:
        print(f"  - skipped empty chunk {chunk_obj.object_name}")

print(f"\nTotal audio: {len(combined)} bytes. Sending to OpenRouter Whisper...")
api_key = os.getenv('OPENROUTER_API_KEY')

with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
    tmp.write(combined)
    tmp_path = tmp.name

with open(tmp_path, 'rb') as f:
    resp = requests.post(
        'https://openrouter.ai/api/v1/audio/transcriptions',
        headers={'Authorization': f'Bearer {api_key}'},
        files={'file': ('audio.webm', f, 'audio/webm')},
        data={'model': os.getenv('OPENROUTER_STT_MODEL', 'openai/whisper-1'), 'response_format': 'json'},
        timeout=120
    )
os.unlink(tmp_path)

print(f"OpenRouter status: {resp.status_code}")
if resp.status_code == 200:
    transcript = resp.json().get('text', '').strip()
    print(f"\nTRANSCRIPT:\n{transcript}\n")
    update_interview_status(INTERVIEW_ID, 'COMPLETED', transcript_text=transcript)
    print(f"Saved to interview id={INTERVIEW_ID} - DONE")
else:
    print(f"Error: {resp.text}")

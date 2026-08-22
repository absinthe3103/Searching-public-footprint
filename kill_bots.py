import requests, os
from dotenv import load_dotenv
load_dotenv()

VEXA_URL = os.getenv('VEXA_API_URL', 'http://localhost:18056')
VEXA_KEY = os.getenv('VEXA_API_KEY', '')
headers = {'X-API-Key': VEXA_KEY}

r = requests.get(f'{VEXA_URL}/bots', headers=headers)
bots = r.json().get('meetings', [])

stuck_statuses = ['requested', 'joining', 'active', 'processing']
stuck = [b for b in bots if b['status'] in stuck_statuses]
print(f"Found {len(stuck)} stuck bot(s):")
for b in stuck:
    print(f"  id={b['id']} status={b['status']} meet={b['native_meeting_id']}")

for b in stuck:
    bot_id = b['id']
    stop = requests.delete(f'{VEXA_URL}/bots/{bot_id}', headers=headers)
    print(f"  DELETE /bots/{bot_id}: {stop.status_code} - {stop.text[:100]}")

print("Done! Verifying remaining stuck bots...")
r2 = requests.get(f'{VEXA_URL}/bots', headers=headers)
bots2 = r2.json().get('meetings', [])
still_stuck = [b for b in bots2 if b['status'] in stuck_statuses]
print(f"Remaining stuck bots: {len(still_stuck)}")

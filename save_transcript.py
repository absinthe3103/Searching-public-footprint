import sys, os
sys.path.insert(0, 'Backend/database')
from dotenv import load_dotenv
load_dotenv()
from db import get_interviews, update_interview_status

TRANSCRIPT = """ I'm Mok Shao Ming and I am 21 years old and currently studying software engineering at University of Guadalajara, Utah where I maintain a CGPA of 3.48 and I am deeply passionate about AI, artificial intelligence and how it can be engineered to automate complex real-world workflows. To put my skills into practice, I recently built an end-to-end AI power hiring system. In this project, I integrated a self-hosted meeting bot to automatically join Google Meet and capture live audio transcripts. I built a fast API backend to process the data and utilize large language models, LLM specifically, like Google Gemini, Cloud, like OnlineMarket. to analyze the transcripts and dynamically generate a fully structured PDF resume on Next.js. So building this system hands-on gave me a strong practical experience in LLM integration, so back architecture and also the full development I eager to bring this same builder mindset and technical curiosity to the AI engineer internship role at your company I would love the opportunity to contribute to your AI solutions while learning from a team of experts. Thank you for your time, and I look forward to speaking with you."""

interviews = get_interviews()
print("Current interviews:")
for i in interviews:
    print(f"  id={i['id']} | {i['candidate_name']} | status={i['status']}")

# Save to the most recent SCHEDULED interview (or any that hasn't been completed)
target = None
for i in interviews:
    if i['status'] in ('SCHEDULED', 'PROCESSING'):
        target = i
        break

if not target:
    # fallback: latest interview
    target = interviews[0] if interviews else None

if target:
    update_interview_status(target['id'], 'COMPLETED', transcript_text=TRANSCRIPT)
    print(f"\nSaved transcript to interview id={target['id']} ({target['candidate_name']})")
    print("Status set to COMPLETED — Generate CV button will now appear!")
else:
    print("No interview found to update.")

"""
Logic.py
FastAPI backend for the HIRE SYSTEM.

Endpoints:
  POST /evaluate        - Run full pipeline for one candidate
  GET  /candidates      - Return all scored candidates (leaderboard)
  GET  /candidates/{id} - Return single candidate result

Request body for /evaluate:
  {
    "candidate_name": "John Doe",
    "job_requirements": ["Python", "Machine Learning", "3+ years backend"]
  }

Response:
  {
    "candidate_name": "John Doe",
    "rescoring_score": 78.5,
    "dimensions": { ... 9 dimension scores ... },
    "reasoning":  { ... one sentence per dimension ... },
    "source_urls": { "github": "...", "linkedin": "...", ... },
    "db_id": 1
  }
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sys
import os
import requests
import json
import tempfile
from typing import Any

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_BACKEND, "AI"))
sys.path.insert(0, os.path.join(_BACKEND, "database"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_AI import evaluate_candidate
from db import (
    get_all_candidates, get_candidate_by_id,
    get_culture_preferences, set_culture_preferences, CULTURE_DIMENSIONS,
    get_preferred_universities, add_preferred_university, delete_preferred_university,
    get_interviews, create_interview, update_interview_status, get_interview_by_id
)

# ──────────────────────────────────────────────────────────
# APP SETUP
# ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Hire System – AI Candidate Evaluator",
    description="Scores candidates across 9 dimensions using public profile data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()

@app.on_event("startup")
def start_scheduler():
    scheduler.start()

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()


# ──────────────────────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────────────────────
class EvaluateRequest(BaseModel):
    candidate_name:   str
    job_requirements: list[str]
    original_role:    str | None = None
    original_tier:    str | None = None
    university:       str | None = None   # optional — candidate's university
    summary_profile:  str | None = None   # optional — free-text paragraph the AI
                                           # uses to score the 7 culture dimensions
    backend:          str = "gemini"   # updated to gemini

    # Optional exact usernames/URLs for each platform
    github_username:            str | None = None
    linkedin_username:          str | None = None
    kaggle_username:            str | None = None
    devto_username:             str | None = None
    medium_username:            str | None = None
    hashnode_username:          str | None = None
    google_scholar_identifier:  str | None = None
    researchgate_identifier:    str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "candidate_name":   "Andrew Ng",
                "original_role":    "Senior Research Scientist",
                "original_tier":    "Tier 1",
                "job_requirements": [
                    "Machine Learning",
                    "Python",
                    "Deep Learning",
                    "Published research",
                ],
                "backend": "gemini",
                "github_username": "andrewyng",
                "linkedin_username": "andrewyng"
            }
        }
    }


class DimensionScores(BaseModel):
    technical_competency:  int
    problem_solving:       int
    communication:         int
    career_stability:      int
    company_exposure:      int
    academic_signal:       int
    initiative:            int
    risk_indicators:       int
    role_domain_relevance: int


class SourceURLs(BaseModel):
    github:         str | None
    linkedin:       str | None
    google_scholar: str | None
    researchgate:   str | None
    kaggle:         str | None
    devto:          str | None
    medium:         str | None
    hashnode:       str | None


class EvaluateResponse(BaseModel):
    candidate_name:  str
    original_role:   str | None
    original_tier:   str | None
    university:      str | None = None
    summary_profile: str | None = None
    rescoring_score: float
    dimensions:      DimensionScores
    culture_fit_dimensions: list[str] = []   # e.g. ["team_orientation", "stability"]
    reasoning:       dict
    source_urls:     SourceURLs
    source_details:  dict[str, Any]
    db_id:           int
    scoring_failed:  bool = False
    
    # Enrichment fields — nullable when AI scoring fails
    fit_direction:         str | None = None
    whats_changed_summary: str | None = None
    re_engage_flag:        bool | None = None
    status:                str | None = None
    executive_summary:     str | None = None
    possible_profiles:     dict[str, list[str]] = {}


class CandidateRow(BaseModel):
    id:   int
    name: str
    original_role:   str | None = None
    original_tier:   str | None = None
    university:      str | None = None
    summary_profile: str | None = None

    # Source usernames
    github_username:   str | None = None
    linkedin_username: str | None = None
    kaggle_username:   str | None = None
    devto_username:    str | None = None
    medium_username:   str | None = None
    hashnode_username: str | None = None

    # 9 dimension scores
    technical_competency:  float
    problem_solving:       float
    communication:         float
    career_stability:      float
    company_exposure:      float
    academic_signal:       float
    initiative:            float
    risk_indicators:       float
    role_domain_relevance: float

    # Culture dimensions the AI matched from the candidate's summary_profile
    # (empty list when no summary_profile was given)
    culture_fit_dimensions: list[str] = []

    # Enrichment fields
    fit_direction:         str | None = None
    whats_changed_summary: str | None = None
    re_engage_flag:        bool | None = None
    status:                str | None = None
    executive_summary:     str | None = None

    created_at: str


class TalentRadarCandidate(CandidateRow):
    """CandidateRow + why this candidate was surfaced by HR's Preferences
    settings, so the ranking boost stays visible rather than silently
    folded into rescoring_score."""
    university_match:          bool = False
    matched_culture_dimensions: list[str] = []
    preference_match:          bool = False


class CulturePreferencesUpdate(BaseModel):
    """selected: the list of culture dimension keys HR has marked as relevant
    (chip multi-select) — any dimension not listed is turned off."""
    selected: list[str]


class NewUniversity(BaseModel):
    name: str


class PreferredUniversityRow(BaseModel):
    id:         int
    name:       str
    created_at: str


class NewInterview(BaseModel):
    title: str
    candidate_name: str
    google_meet_link: str
    date: str
    scheduled_time: str
    description: str = ""


class InterviewRow(BaseModel):
    id: int
    title: str
    description: str | None
    candidate_name: str
    google_meet_link: str | None
    scheduled_time: str | None
    date: str | None
    status: str
    transcript_text: str | None
    generated_cv_url: str | None
    created_at: str


class VexaWebhookPayload(BaseModel):
    meet_url: str
    transcript: str


# ──────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Hire System API is running."}


@app.post("/evaluate", response_model=EvaluateResponse, tags=["Evaluation"])
async def evaluate(req: EvaluateRequest):
    """
    Full pipeline:
    1. Search candidate's public profiles (GitHub, LinkedIn, Scholar, etc.)
    2. Send collected data to the chosen LLM backend (OpenRouter or local Ollama) for 9-dimension scoring
    3. Compute weighted rescoring score
    4. Save to DB
    5. Return score + dimensions + source URLs
    """
    if not req.candidate_name.strip():
        raise HTTPException(status_code=400, detail="candidate_name cannot be empty.")
    if not req.job_requirements:
        raise HTTPException(status_code=400, detail="job_requirements cannot be empty.")
    if req.backend not in ("openrouter", "ollama", "gemini"):
        raise HTTPException(
            status_code=400,
            detail=f"backend must be 'openrouter', 'ollama', or 'gemini', got '{req.backend}'."
        )

    usernames = {
        "github_username":           req.github_username,
        "linkedin_username":         req.linkedin_username,
        "kaggle_username":           req.kaggle_username,
        "devto_username":            req.devto_username,
        "medium_username":           req.medium_username,
        "hashnode_username":         req.hashnode_username,
        "google_scholar_identifier": req.google_scholar_identifier,
        "researchgate_identifier":   req.researchgate_identifier,
    }

    result = evaluate_candidate(
        candidate_name=req.candidate_name.strip(),
        requirements=req.job_requirements,
        backend=req.backend,
        usernames=usernames,
        original_role=req.original_role,
        original_tier=req.original_tier,
        university=req.university,
        summary_profile=req.summary_profile,
    )

    # result is None only if backend name was invalid or a fatal error occurred
    if not result or "sources" not in result:
        raise HTTPException(
            status_code=502,
            detail="Pipeline failed: could not collect any public profile data."
        )

    scores  = result.get("scores", {})
    sources = result.get("sources", {})

    # Build dimension scores (strip reasoning key)
    dim_keys = [
        "technical_competency", "problem_solving", "communication",
        "career_stability", "company_exposure", "academic_signal",
        "initiative", "risk_indicators", "role_domain_relevance",
    ]
    dimensions = {k: scores.get(k, 0) for k in dim_keys}
    # AI returns a list of dimension keys it judged the summary_profile fits,
    # e.g. ["team_orientation", "stability"]. Filter to only known keys so a
    # stray/invalid value from the model can't leak into the DB or response.
    culture_fit_dimensions = [
        d for d in scores.get("culture_fit_dimensions", []) if d in CULTURE_DIMENSIONS
    ]
    reasoning  = scores.get("reasoning", {})

    # Extract source URLs
    source_urls = {
        "github":         sources.get("github",         {}).get("profile_url"),
        "linkedin":       sources.get("linkedin",       {}).get("profile_url"),
        "google_scholar": sources.get("google_scholar", {}).get("profile_url"),
        "researchgate":   sources.get("researchgate",   {}).get("profile_url"),
        "kaggle":         sources.get("kaggle",         {}).get("profile_url"),
        "devto":          sources.get("devto",          {}).get("profile_url"),
        "medium":         sources.get("medium",         {}).get("profile_url"),
        "hashnode":       sources.get("hashnode",       {}).get("profile_url"),
    }

    source_details = {
        key: {
            "profile_url": value.get("profile_url"),
            "summary": value.get("summary"),
            "latest_push": value.get("latest_push"),
            "contribution_activity": value.get("contribution_activity"),
            "current_role": value.get("current_role"),
            "company": value.get("company"),
            "citations": value.get("citations"),
            "interests": value.get("interests"),
            "publications": value.get("publications"),
            "articles": value.get("articles"),
            "top_languages": value.get("top_languages"),
            "keyword_hits": value.get("keyword_hits"),
            "repos": value.get("repos", []),
            "writeups": value.get("writeups", []),
            "pinned_works": value.get("pinned_works", []),
        }
        for key, value in sources.items()
    }

    possible_profiles = {
        key: value.get("possible_profiles", [])
        for key, value in sources.items()
        if value.get("possible_profiles")
    }

    return EvaluateResponse(
        candidate_name=req.candidate_name,
        original_role=req.original_role,
        original_tier=req.original_tier,
        university=req.university,
        summary_profile=req.summary_profile,
        rescoring_score=result["rescoring_score"],
        dimensions=DimensionScores(**dimensions),
        culture_fit_dimensions=culture_fit_dimensions,
        reasoning=reasoning,
        source_urls=SourceURLs(**source_urls),
        source_details=source_details,
        db_id=result.get("db_id", -1),
        scoring_failed=result.get("scoring_failed", False),
        fit_direction=scores.get("fit_direction"),
        whats_changed_summary=scores.get("whats_changed_summary"),
        re_engage_flag=scores.get("re_engage_flag"),
        status=scores.get("status"),
        executive_summary=scores.get("executive_summary"),
        possible_profiles=possible_profiles,
    )


@app.get("/candidates", response_model=list[CandidateRow], tags=["Candidates"])
def list_candidates():
    """Return all evaluated candidates sorted by score (highest first)."""
    return get_all_candidates()


@app.get("/candidates/prioritized", response_model=list[TalentRadarCandidate], tags=["Candidates"])
def list_candidates_prioritized():
    """Talent Radar view: candidates matching HR's preferred universities
    and/or selected culture dimensions (set on the Preferences page) are
    surfaced first. Each candidate carries university_match /
    matched_culture_dimensions so the boost is visible, not a hidden
    reshuffle of the score. Within each group (matched vs. not), the
    existing role_domain_relevance ordering is preserved."""
    candidates = get_all_candidates()
    preferred_unis = {u["name"].strip().lower() for u in get_preferred_universities()}
    culture_prefs = get_culture_preferences()
    selected_dims = {dim for dim, on in culture_prefs.items() if on}

    annotated = []
    for c in candidates:
        uni = (c.get("university") or "").strip().lower()
        university_match = bool(uni) and uni in preferred_unis
        matched_dims = [d for d in c.get("culture_fit_dimensions", []) if d in selected_dims]
        annotated.append({
            **c,
            "university_match": university_match,
            "matched_culture_dimensions": matched_dims,
            "preference_match": university_match or bool(matched_dims),
        })

    # Stable sort: preference matches float to the top; get_all_candidates()
    # already orders by role_domain_relevance DESC, and Python's sort is
    # stable, so that ordering is preserved within each group.
    annotated.sort(key=lambda c: not c["preference_match"])
    return annotated


@app.get("/candidates/{candidate_id}", response_model=CandidateRow, tags=["Candidates"])
def get_candidate(candidate_id: int):
    """Return a single candidate by DB id."""
    row = get_candidate_by_id(candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Candidate id={candidate_id} not found.")
    return row


# ──────────────────────────────────────────────────────────
# PREFERENCES  (HR settings — culture dimensions + preferred universities)
# ──────────────────────────────────────────────────────────

@app.get("/preferences/culture", tags=["Preferences"])
def get_culture_prefs():
    """Return {dimension: bool} for all 7 culture dimensions — which ones
    HR has selected as relevant via the chip multi-select."""
    return get_culture_preferences()


@app.put("/preferences/culture", tags=["Preferences"])
def update_culture_prefs(body: CulturePreferencesUpdate):
    """Overwrite HR's culture dimension selection.
    body.selected: list of dimension keys that should be ON."""
    unknown = [d for d in body.selected if d not in CULTURE_DIMENSIONS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown culture dimension(s): {unknown}. Valid: {CULTURE_DIMENSIONS}"
        )
    set_culture_preferences(body.selected)
    return get_culture_preferences()


@app.get("/preferences/universities", response_model=list[PreferredUniversityRow], tags=["Preferences"])
def list_preferred_universities():
    """Return all preferred universities, alphabetically."""
    return get_preferred_universities()


@app.post("/preferences/universities", response_model=PreferredUniversityRow, tags=["Preferences"])
def create_preferred_university(body: NewUniversity):
    """Add a preferred university."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="University name cannot be empty.")
    new_id = add_preferred_university(body.name)
    if new_id is None:
        raise HTTPException(status_code=409, detail=f"'{body.name}' is already in the preferred list.")
    return {"id": new_id, "name": body.name.strip(), "created_at": ""}


@app.delete("/preferences/universities/{university_id}", tags=["Preferences"])
def remove_preferred_university(university_id: int):
    """Remove a preferred university by id."""
    deleted = delete_preferred_university(university_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"University id={university_id} not found.")
    return {"status": "ok", "deleted_id": university_id}


# ──────────────────────────────────────────────────────────
# INTERVIEWS
# ──────────────────────────────────────────────────────────

@app.get("/interviews", response_model=list[InterviewRow], tags=["Interviews"])
def list_interviews():
    """Return all interviews for the dashboard."""
    return get_interviews()


def trigger_vexa_bot(meeting_url: str):
    """Fired by the scheduler to make Vexa join the Google Meet"""
    vexa_url = os.getenv("VEXA_API_URL")
    vexa_key = os.getenv("VEXA_API_KEY")
    
    if not vexa_url or not meeting_url:
        return

    # Extract meeting ID from URL (e.g. https://meet.google.com/abc-defg-hij -> abc-defg-hij)
    native_meeting_id = meeting_url.split('/')[-1].split('?')[0]

    try:
        # Vexa documented API schema
        payload = {
            "platform": "google_meet",
            "native_meeting_id": native_meeting_id,
            "bot_name": "HireSystem Note Taker",
            "webhook_url": "http://host.docker.internal:8000/interviews/webhook"
        }
        headers = {
            'Content-Type': 'application/json'
        }
        if vexa_key:
            headers["X-API-Key"] = vexa_key
            
        response = requests.post(
            f"{vexa_url.rstrip('/')}/bots", 
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Vexa Scheduled Trigger: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Warning: Failed to trigger Vexa API - {e}")


@app.post("/interviews", response_model=InterviewRow, tags=["Interviews"])
def add_interview(body: NewInterview):
    """Schedule a new interview and set the Vexa bot alarm."""
    new_id = create_interview(
        title=body.title,
        candidate_name=body.candidate_name,
        google_meet_link=body.google_meet_link,
        date=body.date,
        scheduled_time=body.scheduled_time,
        description=body.description
    )
    row = get_interview_by_id(new_id)
    
    # Trigger Vexa automatically at the scheduled date & time
    if body.google_meet_link and body.date and body.scheduled_time:
        try:
            # Parse 'YYYY-MM-DD' and 'HH:MM' into a python datetime object
            date_str = f"{body.date} {body.scheduled_time}"
            target_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            
            # If the time is already in the past, trigger now. Otherwise, schedule it.
            if target_time <= datetime.now():
                trigger_vexa_bot(body.google_meet_link)
            else:
                scheduler.add_job(
                    trigger_vexa_bot, 
                    'date', 
                    run_date=target_time, 
                    args=[body.google_meet_link]
                )
                print(f"Scheduled Vexa bot to join {body.google_meet_link} at {target_time}")
        except Exception as e:
            print(f"Failed to parse time or schedule bot: {e}")

    return row


from fastapi import Request
from fastapi.concurrency import run_in_threadpool

def _transcribe_via_openrouter(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Send raw audio bytes to OpenRouter's STT endpoint (routed to OpenAI Whisper).
    Uses OPENROUTER_API_KEY from the environment.
    NOTE: OpenRouter requires the model to be namespaced e.g. 'openai/whisper-1',
    NOT just 'whisper-1', otherwise you get silent 404s.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in environment")
    
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as f:
            response = requests.post(
                "https://openrouter.ai/api/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (filename, f, "audio/webm")},
                data={"model": os.getenv("OPENROUTER_STT_MODEL", "openai/whisper-1"), "response_format": "text"},
                timeout=120
            )
        response.raise_for_status()
        return response.text.strip()
    finally:
        os.unlink(tmp_path)


def _download_and_transcribe(session_uid: str) -> str:
    """
    Download all audio chunks for a recording session from MinIO,
    concatenate them, and transcribe using Groq Whisper.
    Returns the full transcript text.
    """
    from minio import Minio
    
    # MinIO connection settings (from Vexa's docker-compose defaults)
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access   = os.getenv("MINIO_ACCESS_KEY", "vexa-access-key")
    minio_secret   = os.getenv("MINIO_SECRET_KEY", "vexa-secret-key")
    minio_bucket   = os.getenv("MINIO_BUCKET", "vexa")
    
    client = Minio(minio_endpoint, access_key=minio_access, secret_key=minio_secret, secure=False)
    
    # List all objects whose name contains the session_uid
    print(f"[MinIO] Searching for recording chunks with session_uid={session_uid}")
    objects = list(client.list_objects(minio_bucket, recursive=True))
    chunks = sorted(
        [o for o in objects if session_uid in o.object_name],
        key=lambda o: o.object_name
    )
    
    if not chunks:
        print(f"[MinIO] No chunks found for session {session_uid}")
        return ""
    
    print(f"[MinIO] Found {len(chunks)} chunk(s): {[c.object_name for c in chunks]}")
    
    # Download and concatenate all chunks
    combined = bytearray()
    for chunk_obj in chunks:
        data = client.get_object(minio_bucket, chunk_obj.object_name)
        chunk_bytes = data.read()
        combined.extend(chunk_bytes)
        print(f"[MinIO] Downloaded chunk {chunk_obj.object_name} ({len(chunk_bytes)} bytes)")
    
    print(f"[MinIO] Total audio size: {len(combined)} bytes — sending to OpenRouter Whisper...")
    transcript = _transcribe_via_openrouter(bytes(combined))
    print(f"[OpenRouter] Transcript: {transcript[:200]}..." if len(transcript) > 200 else f"[OpenRouter] Transcript: {transcript}")
    return transcript


@app.post("/interviews/webhook", tags=["Interviews"])
async def vexa_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint for Vexa. When a meeting ends, Vexa posts here.
    We extract the recording session UID, download audio from MinIO,
    transcribe with Groq Whisper, and save the transcript to DB.
    """
    payload_dict = await request.json()
    print("================ WEBHOOK RECEIVED ================")
    print(json.dumps(payload_dict, indent=2))
    print("==================================================")
    
    # --- Extract key fields from Vexa's payload ---
    # Meet URL (try multiple possible field names)
    meet_url = (
        payload_dict.get("meet_url")
        or payload_dict.get("meeting_url")
        or payload_dict.get("meetingUrl")
        or payload_dict.get("constructed_meeting_url")
    )
    if not meet_url and "data" in payload_dict:
        meet_url = (
            payload_dict["data"].get("meeting_url")
            or payload_dict["data"].get("meet_url")
            or payload_dict["data"].get("constructed_meeting_url")
        )

    # Recording session UID — present in Vexa's completion payload
    session_uid = payload_dict.get("session_uid") or payload_dict.get("recording_session_uid")
    if not session_uid and "data" in payload_dict:
        sessions = payload_dict["data"].get("sessions", [])
        if sessions:
            session_uid = sessions[0]  # Use the first session
    if not session_uid and "sessions" in payload_dict:
        sessions = payload_dict.get("sessions", [])
        if sessions:
            session_uid = sessions[0]

    # Transcript (if Vexa somehow produced one)
    transcript = payload_dict.get("transcript") or payload_dict.get("text")
    if not transcript and "data" in payload_dict:
        transcript = payload_dict["data"].get("transcript") or payload_dict["data"].get("text")

    print(f"[Webhook] meet_url={meet_url}, session_uid={session_uid}, has_transcript={bool(transcript)}")

    # --- Find the matching interview in DB ---
    interviews = get_interviews()
    target_interview = None

    if meet_url:
        # Normalize URL for comparison (strip https://, trailing slashes)
        clean_url = meet_url.replace("https://", "").replace("http://", "").rstrip("/")
        for interview in interviews:
            link = (interview.get("google_meet_link") or "").replace("https://", "").replace("http://", "").rstrip("/")
            if link == clean_url and interview.get("status") == "SCHEDULED":
                target_interview = interview
                break

    if not target_interview:
        # Fallback: pick the most recent SCHEDULED interview
        scheduled = [i for i in interviews if i.get("status") == "SCHEDULED"]
        if scheduled:
            target_interview = scheduled[-1]
            print(f"[Webhook] Matched by fallback to interview id={target_interview['id']}")

    if not target_interview:
        raise HTTPException(status_code=404, detail="Matching scheduled interview not found.")

    interview_id = target_interview["id"]

    # --- If no transcript from Vexa, download audio from MinIO and transcribe with Groq ---
    if not transcript and session_uid:
        print(f"[Webhook] No transcript from Vexa. Downloading audio (session={session_uid}) for Groq transcription...")
        update_interview_status(interview_id, "PROCESSING")
        
        def do_transcription():
            try:
                text = _download_and_transcribe(session_uid)
                update_interview_status(interview_id, "COMPLETED", transcript_text=text or "[No speech detected]")
                print(f"[Webhook] Transcript saved for interview {interview_id}")
            except Exception as e:
                print(f"[Webhook] Transcription failed: {e}")
                update_interview_status(interview_id, "COMPLETED", transcript_text=f"[Transcription failed: {e}]")
        
        background_tasks.add_task(do_transcription)
        return {"status": "processing", "message": f"Downloading and transcribing audio for interview {interview_id}"}
    
    # --- Vexa provided a transcript directly — save it ---
    final_transcript = transcript if transcript else json.dumps(payload_dict)
    update_interview_status(interview_id, "COMPLETED", transcript_text=final_transcript)
    return {"status": "ok", "message": f"Transcript saved for interview {interview_id}"}


class GenerateResumeRequest(BaseModel):
    interview_id: int

@app.post("/interviews/generate-cv", tags=["Interviews"])
def generate_cv(req: GenerateResumeRequest):
    """
    Given a completed interview ID, take its transcript and ask the LLM to structure it into a CV JSON.
    """
    row = get_interview_by_id(req.interview_id)
    if not row:
        raise HTTPException(status_code=404, detail="Interview not found")
    if not row.get("transcript_text"):
        raise HTTPException(status_code=400, detail="No transcript available for this interview")
        
    import json as _json
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    prompt = f"""You are a professional CV/Resume writer. Extract ALL information from the transcript below and return a structured JSON.
Return ONLY a raw JSON object — no markdown, no code blocks, no explanation.

JSON structure to follow EXACTLY:
{{
  "name": "Full legal name",
  "phone": "Phone number if mentioned, else empty string",
  "email": "Email address if mentioned, else empty string",
  "linkedin": "LinkedIn URL or username if mentioned, else empty string",
  "github": "GitHub URL or username if mentioned, else empty string",
  "summary": "3-4 sentence professional summary. Mention their year of study, degree, university, CGPA, passion areas, key skills, and career goal.",
  "education": [
    {{
      "degree": "Full degree title e.g. Bachelor Degree of Software Engineering",
      "institution": "University name",
      "start_date": "Month Year e.g. June 2024",
      "end_date": "Month Year or Current e.g. June 2027 (Current)",
      "location": "City, Country e.g. Selangor, Malaysia",
      "cgpa": "CGPA value e.g. 3.48"
    }}
  ],
  "competitions": [
    {{
      "name": "Competition name",
      "date": "Month Year",
      "location": "Location",
      "role": "Participant or Team Lead etc",
      "project": "Project name if any",
      "bullets": ["Achievement or responsibility 1", "Achievement or responsibility 2"]
    }}
  ],
  "projects": [
    {{
      "name": "Project name",
      "tech_stack": "Technologies used e.g. FastAPI, Next.js, Docker",
      "bullets": ["What was built or achieved 1", "What was built or achieved 2", "What was built or achieved 3"]
    }}
  ],
  "academic_awards": ["Award 1", "Award 2"],
  "technical_skills": {{
    "languages": "e.g. Python, JavaScript, Java",
    "frameworks": "e.g. FastAPI, React, Next.js",
    "developer_tools": "e.g. Git, Docker, VS Code",
    "libraries": "e.g. Pandas, NumPy, LangChain"
  }}
}}

CANDIDATE NAME: {row.get('candidate_name')}

TRANSCRIPT:
{row.get('transcript_text')}

IMPORTANT RULES:
- Extract every project, technology, skill, and achievement the candidate mentioned.
- If they mention building a system or app, add it to projects with detailed bullet points.
- For education, infer reasonable start/end dates based on what they say.
- technical_skills must be comma-separated strings in each category.
- competitions and academic_awards can be empty arrays [] if none mentioned.
- If a field is unknown, use an empty string or empty array.
- Return ONLY the raw JSON object."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "HireSystem"
            },
            json={
                "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=60
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")


# ──────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("Logic:app", host="0.0.0.0", port=8000, reload=True)
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
import sys
import os
from typing import Any

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_BACKEND, "AI"))
sys.path.insert(0, os.path.join(_BACKEND, "database"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_AI import evaluate_candidate
from db import get_all_candidates, get_candidate_by_id

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


# ──────────────────────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────────────────────
class EvaluateRequest(BaseModel):
    candidate_name:   str
    job_requirements: list[str]
    backend:          str = "openrouter"   # "openrouter" or "ollama"

    # Optional exact usernames/URLs for each platform
    github_username:            str | None = None
    linkedin_username:          str | None = None
    kaggle_username:            str | None = None
    devto_username:             str | None = None
    medium_username:            str | None = None
    hashnode_username:          str | None = None
    # Scholar: Google Scholar user ID, Semantic Scholar author ID/URL, or full URL
    google_scholar_identifier:  str | None = None
    # ResearchGate: profile slug, ORCID iD (xxxx-xxxx-xxxx-xxxx), or full URL
    researchgate_identifier:    str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "candidate_name":   "Andrew Ng",
                "job_requirements": [
                    "Machine Learning",
                    "Python",
                    "Deep Learning",
                    "Published research",
                ],
                "backend": "openrouter",
                "github_username": "andrewyng",
                "linkedin_username": "andrewyng",
                "kaggle_username": None,
                "devto_username": None,
                "medium_username": None,
                "hashnode_username": None
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
    rescoring_score: float
    dimensions:      DimensionScores
    reasoning:       dict
    source_urls:     SourceURLs
    source_details:  dict[str, Any]
    db_id:           int
    scoring_failed:  bool = False   # True when AI scoring was skipped


class CandidateRow(BaseModel):
    id:   int
    name: str

    # Source usernames
    github_username:   str | None = None
    linkedin_username: str | None = None
    kaggle_username:   str | None = None
    devto_username:    str | None = None
    medium_username:   str | None = None
    hashnode_username: str | None = None

    # 9 dimension scores (replaces the old single rescoring_score column)
    technical_competency:  float
    problem_solving:       float
    communication:         float
    career_stability:      float
    company_exposure:      float
    academic_signal:       float
    initiative:            float
    risk_indicators:       float
    role_domain_relevance: float

    created_at: str


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
    if req.backend not in ("openrouter", "ollama"):
        raise HTTPException(
            status_code=400,
            detail=f"backend must be 'openrouter' or 'ollama', got '{req.backend}'."
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

    return EvaluateResponse(
        candidate_name=req.candidate_name,
        rescoring_score=result["rescoring_score"],
        dimensions=DimensionScores(**dimensions),
        reasoning=reasoning,
        source_urls=SourceURLs(**source_urls),
        source_details=source_details,
        db_id=result.get("db_id", -1),
        scoring_failed=result.get("scoring_failed", False),
    )


@app.get("/candidates", response_model=list[CandidateRow], tags=["Candidates"])
def list_candidates():
    """Return all evaluated candidates sorted by score (highest first)."""
    return get_all_candidates()


@app.get("/candidates/{candidate_id}", response_model=CandidateRow, tags=["Candidates"])
def get_candidate(candidate_id: int):
    """Return a single candidate by DB id."""
    row = get_candidate_by_id(candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Candidate id={candidate_id} not found.")
    return row


# ──────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("logic:app", host="0.0.0.0", port=8000, reload=True)
"""
api_AI.py
Orchestrates the full pipeline:
  1. Run candidate_searcher to collect public profile data
  2. Send collected data to an LLM backend (OpenRouter or local Ollama) for 9-dimension scoring
  3. Save candidate name + rescoring score to DB

9 Scoring Dimensions (0-100 each):
  - Technical Competency
  - Problem Solving
  - Communication
  - Career Stability
  - Company Exposure
  - Academic Signal
  - Initiative
  - Risk Indicators     (subtracted)
  - Role Domain Relevance (primary signal / weighted higher)
"""

import json
import sys
import os
import requests
import time
import re
from pydantic import BaseModel, Field

# Ensure Windows terminal encoding errors never crash print statements
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

from google import genai
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Import siblings ──────────────────────────────────────
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_BACKEND, "database"))
sys.path.insert(0, os.path.join(_BACKEND, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import insert_candidate, get_all_candidates, get_candidate_by_id, update_candidate

# ── OpenRouter API ───────────────────────────────────────
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6")

# ── Local Ollama ─────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.1")

# ── Dimension keys (must match Backend/database/db.py DIMENSION_COLUMNS) ──
DIMENSION_KEYS = [
    "technical_competency", "problem_solving", "communication",
    "career_stability", "company_exposure", "academic_signal",
    "initiative", "risk_indicators", "role_domain_relevance",
]

# ── Dimension weights ────────────────────────────────────
WEIGHTS = {
    "technical_competency":   0.15,
    "problem_solving":        0.10,
    "communication":          0.10,
    "career_stability":       0.08,
    "company_exposure":       0.08,
    "academic_signal":        0.10,
    "initiative":             0.09,
    "risk_indicators":       -0.10,   # subtracted
    "role_domain_relevance":  0.30,   # primary signal
}

# ── Pydantic Schemas for Gemini ───────────────────────────────────────
class Reasoning(BaseModel):
    technical_competency: str = Field(description="One sentence reasoning")
    problem_solving: str = Field(description="One sentence reasoning")
    communication: str = Field(description="One sentence reasoning")
    career_stability: str = Field(description="One sentence reasoning")
    company_exposure: str = Field(description="One sentence reasoning")
    academic_signal: str = Field(description="One sentence reasoning")
    initiative: str = Field(description="One sentence reasoning")
    risk_indicators: str = Field(description="One sentence reasoning")
    role_domain_relevance: str = Field(description="One sentence reasoning")

class CandidateEvaluation(BaseModel):
    technical_competency: int = Field(description="Score 0-100")
    problem_solving: int = Field(description="Score 0-100")
    communication: int = Field(description="Score 0-100")
    career_stability: int = Field(description="Score 0-100")
    company_exposure: int = Field(description="Score 0-100")
    academic_signal: int = Field(description="Score 0-100")
    initiative: int = Field(description="Score 0-100")
    risk_indicators: int = Field(description="Score 0-100")
    role_domain_relevance: int = Field(description="Score 0-100")
    reasoning: Reasoning
    
    # Enrichment Fields
    fit_direction: str = Field(description="improved, declined, or unchanged")
    whats_changed_summary: str = Field(description="A plain-language explanation of what changed in their public footprint")
    re_engage_flag: bool = Field(description="True if it is a good time to re-engage, False otherwise")
    status: str = Field(description="One of: 'Active opportunity', 'Re-engage', 'Watch', 'Faded'")
    ai_summary: str = Field(description="A 2-3 paragraph natural language summary based on retrieved information, assessing their fit for the position (culture, workforce, tech skills, language, collaboration).")
    top_strengths: list[str] = Field(description="Exactly 3 key strengths of this candidate.")
    top_weaknesses: list[str] = Field(description="Exactly 3 key weaknesses or concerns for this candidate.")

class LifestyleSocials(BaseModel):
    facebook: str = Field(description="URL to Facebook profile, or 'no account found'")
    instagram: str = Field(description="URL to Instagram profile, or 'no account found'")
SCORING_SYSTEM_PROMPT = """
You are the HINT Master Persona, an expert AI hiring evaluator. You will receive a candidate's public profile data
collected from GitHub, LinkedIn, Google Scholar, ResearchGate, Kaggle, Dev.to, Medium,
and Hashnode, along with the job requirements and their original role.

Evaluate the candidate across exactly the 9 dimensions (score 0-100).
Role domain relevance is the PRIMARY signal.

If a RUBRIC is provided, you MUST strictly follow its scoring baselines for the relevant dimensions.
If HISTORICAL DATA is provided, compare the current data against the history to accurately determine `fit_direction`, `whats_changed_summary`, and `re_engage_flag`.
Otherwise, evaluate these based on their current standing.

Additionally, determine their talent radar status (Active opportunity, Re-engage, Watch, Faded) based on their signals.
Finally, provide a 2-3 paragraph `ai_summary` assessing their fit for the position, covering culture, workforce, tech skills, language, and collaborative potential based on the provided footprint data.
Also extract EXACTLY 3 key strengths into `top_strengths` and 3 weaknesses/concerns into `top_weaknesses`.
"""


# ──────────────────────────────────────────────────────────
# STEP 1: Collect candidate data via searcher
# ──────────────────────────────────────────────────────────
def collect_candidate_data(candidate_name: str, requirements: list[str],
                           usernames: dict | None = None) -> tuple[dict, list]:
    """
    Import and run the candidate searcher inline.
    Returns the full sources dict.

    usernames: optional dict of explicit handles, e.g.
        {"github_username": "octocat", "kaggle_username": "andrewng"}
    When a platform username is provided it is tried directly first,
    bypassing the full-name search for that platform.
    """
    print(f"\n{'='*60}")
    print(f"  STEP 1 — Collecting public profile data")
    print(f"{'='*60}")

    # Import searcher functions
    from candidateSearcher import (
        search_github, search_linkedin, search_google_scholar,
        search_researchgate, search_kaggle, search_devto,
        search_medium, search_hashnode, STOP
    )

    # Extract keywords from requirements
    kws = []
    for req in requirements:
        for w in re.split(r"[\s,/+()\-]+", req.lower()):
            if w and w not in STOP and len(w) > 2:
                kws.append(w)
    kws = list(dict.fromkeys(kws))
    print(f"  Keywords: {kws}\n")

    u = usernames or {}

    # Pass each platform's username as the 'identifier' argument.
    # The individual search_* functions already implement the logic:
    #   if identifier given → try it directly first, skip name-based guess.
    sources = {}
    sources["github"]         = search_github(candidate_name, kws, u.get("github_username"));     time.sleep(1.2)
    sources["linkedin"]       = search_linkedin(candidate_name, kws, u.get("linkedin_username")); time.sleep(1.2)
    sources["google_scholar"] = search_google_scholar(candidate_name, kws, u.get("google_scholar_identifier")); time.sleep(1.2)
    sources["researchgate"]   = search_researchgate(candidate_name, kws, u.get("researchgate_identifier"));   time.sleep(1.2)
    sources["kaggle"]         = search_kaggle(candidate_name, kws, u.get("kaggle_username"));     time.sleep(1.2)
    sources["devto"]          = search_devto(candidate_name, kws, u.get("devto_username"));       time.sleep(1.2)
    sources["medium"]         = search_medium(candidate_name, kws, u.get("medium_username"));     time.sleep(1.2)
    sources["hashnode"]       = search_hashnode(candidate_name, kws, u.get("hashnode_username"))

    return sources, kws


# ──────────────────────────────────────────────────────────
# STEP 2: Build AI prompt from collected data
# ──────────────────────────────────────────────────────────
def build_prompt(candidate_name: str, requirements: list[str],
                 sources: dict, kws: list[str], 
                 original_role: str = "",
                 rubric: dict | None = None,
                 history: dict | None = None) -> str:

    def src_summary(key: str) -> str:
        d = sources.get(key, {})
        lines = [f"  Summary: {d.get('summary', 'N/A')}"]
        if d.get("profile_url"):
            lines.append(f"  URL: {d['profile_url']}")
        if d.get("bio"):
            lines.append(f"  Bio: {d['bio']}")
        if d.get("top_languages"):
            lines.append(f"  Top Languages: {d['top_languages']}")
        if d.get("repos"):
            repo_names = [r["name"] for r in d["repos"][:5]]
            lines.append(f"  Top Repos: {repo_names}")
        if d.get("publications"):
            pub_titles = [p["title"] for p in d["publications"][:5]]
            lines.append(f"  Publications: {pub_titles}")
        if d.get("citations"):
            lines.append(f"  Citations: {d['citations']}")
        if d.get("interests"):
            lines.append(f"  Research Interests: {d['interests']}")
        if d.get("current_role"):
            lines.append(f"  Current Role: {d['current_role']} @ {d.get('company','?')}")
        if d.get("articles"):
            tags = list({t for a in d["articles"][:5] for t in a.get("tags", [])})
            lines.append(f"  Article Tags: {tags}")
        kw_hits = [k for k, v in d.get("keyword_hits", {}).items() if v]
        if kw_hits:
            lines.append(f"  Keywords matched: {kw_hits}")
        return "\n".join(lines)

    prompt = f"""
CANDIDATE: {candidate_name}
ORIGINAL ROLE: {original_role or 'Unknown'}

JOB REQUIREMENTS:
{chr(10).join(f"- {r}" for r in requirements)}

EXTRACTED KEYWORDS: {kws}

{'RUBRIC FOR ' + original_role + ':' + chr(10) + json.dumps(rubric, indent=2) if rubric else ''}

{'HISTORICAL DATA (Last Evaluation):' + chr(10) + json.dumps({k:v for k,v in history.items() if k not in ['id', 'created_at', 'hint_id']}, indent=2) if history else ''}

PUBLIC PROFILE DATA:

[GitHub]
{src_summary('github')}

[LinkedIn]
{src_summary('linkedin')}

[Google Scholar]
{src_summary('google_scholar')}

[ResearchGate]
{src_summary('researchgate')}

[Kaggle]
{src_summary('kaggle')}

[Dev.to]
{src_summary('devto')}

[Medium]
{src_summary('medium')}

[Hashnode]
{src_summary('hashnode')}

Based on all the above, score this candidate and evaluate their re-engagement status.
"""
    return prompt.strip()


# ──────────────────────────────────────────────────────────
# STEP 3: Call Gemini for scoring (Structured JSON)
# ──────────────────────────────────────────────────────────
def call_gemini(prompt: str) -> dict:
    print(f"\n{'═'*60}")
    print(f"  STEP 2 — Sending to Gemini (gemini-flash-latest) for scoring")
    print(f"{'═'*60}")

    if not GEMINI_API_KEY:
        print("  ⚠ GEMINI_API_KEY is not set in .env")
        return {}

    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=SCORING_SYSTEM_PROMPT,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=CandidateEvaluation,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"  ⚠ Gemini Call Failed: {e}")
        return {}


def search_lifestyle_socials(candidate_name: str, requirements: list[str]) -> dict:
    """Uses DuckDuckGo to find lifestyle social media accounts."""
    print(f"\n{'═'*60}")
    print(f"  STEP X — Searching for Lifestyle Socials (FB/IG)")
    print(f"{'═'*60}")
    
    from candidateSearcher import find_profile_url_via_ddg
    
    facebook_url = find_profile_url_via_ddg(candidate_name, "facebook", requirements)
    instagram_url = find_profile_url_via_ddg(candidate_name, "instagram", requirements)
    
    return {
        "facebook": facebook_url if facebook_url else "no account found",
        "instagram": instagram_url if instagram_url else "no account found"
    }


def evaluate_candidate(candidate_name: str, requirements: list[str],
                       backend: str = "gemini",
                       usernames: dict | None = None,
                       original_role: str = "",
                       candidate_id: int | None = None) -> dict | None:
    """
    Run the full extraction -> prompt generation -> Gemini scoring pipeline.
    Returns a dict with dimensions, final score, reasoning, sources, and DB ID.
    """
    if not candidate_name.strip():
        print("⚠ No candidate name provided. Aborting.")
        return None
    if not requirements:
        print("⚠ No requirements provided. Aborting.")
        return None

    # 1. Search profiles
    sources, kws = collect_candidate_data(candidate_name, requirements, usernames)
    if not any(sources.values()):
        print("⚠ No profiles found across any platform. Aborting.")
        return None

    # 2. Load Rubric and History
    rubric = None
    try:
        rubric_path = os.path.join(os.path.dirname(__file__), 'rubrics.json')
        if os.path.exists(rubric_path):
            with open(rubric_path, 'r') as f:
                rubrics_data = json.load(f)
                
                # Support both flat and nested JSON structures
                rubric_dict = rubrics_data.get("rubric", rubrics_data) if isinstance(rubrics_data, dict) else {}
                
                # Fuzzy matching for roles (e.g. "Backend Engineer" -> "Back-end Developer")
                search_role = original_role.lower().replace("-", "").replace(" ", "")
                for key, val in rubric_dict.items():
                    key_clean = key.lower().replace("-", "").replace(" ", "")
                    # If 'backend' is in both, or they match exactly
                    if key_clean == search_role or (search_role and (search_role in key_clean or key_clean in search_role)):
                        rubric = val
                        break
    except Exception as e:
        print(f"  ⚠ Failed to load rubric: {e}")

    history = get_candidate_by_id(candidate_id) if candidate_id else None

    # 3. Build prompt
    prompt = build_prompt(candidate_name, requirements, sources, kws, original_role, rubric, history)

    # 4. Call AI
    scores = call_gemini(prompt)

    scoring_failed = False
    if not scores:
        print("⚠ AI scoring returned empty or failed. Using 0 for all dimensions.")
        scores = {k: 0 for k in DIMENSION_KEYS}
        scores["reasoning"] = {k: "AI evaluation failed" for k in DIMENSION_KEYS}
        scores["fit_direction"] = "unchanged"
        scores["whats_changed_summary"] = "AI evaluation failed"
        scores["re_engage_flag"] = False
        scores["status"] = "Watch"
        scores["ai_summary"] = "AI evaluation failed"
        scores["top_strengths"] = []
        scores["top_weaknesses"] = []
        scoring_failed = True

    # 5. Compute final rescoring score
    rescoring_score = 0.0
    for dim, weight in WEIGHTS.items():
        s = scores.get(dim, 0)
        # Risk indicators are subtracted, all others added
        if weight < 0:
            rescoring_score -= s * abs(weight)
        else:
            rescoring_score += s * weight

    # Cap between 0 and 100
    rescoring_score = max(0.0, min(100.0, rescoring_score))

    print(f"\n{'═'*60}")
    print(f"  STEP 3 — Final Candidate Score: {rescoring_score:.1f}/100")
    print(f"{'═'*60}")

    # 6. Extract usernames and save to DB
    u_save = {
        "github_username":   sources.get("github", {}).get("username"),
        "linkedin_username": sources.get("linkedin", {}).get("username"),
        "kaggle_username":   sources.get("kaggle", {}).get("username"),
        "devto_username":    sources.get("devto", {}).get("username"),
        "medium_username":   sources.get("medium", {}).get("username"),
        "hashnode_username": sources.get("hashnode", {}).get("username"),
    }

    if candidate_id:
        # Update existing
        update_candidate(
            candidate_id=candidate_id,
            dimensions=scores,
            usernames=u_save,
            fit_direction=scores.get("fit_direction", ""),
            whats_changed_summary=scores.get("whats_changed_summary", ""),
            re_engage_flag=scores.get("re_engage_flag", False),
            status=scores.get("status", "")
        )
        returned_db_id = candidate_id
        print(f"  ✓ Updated existing database row for id {returned_db_id}")
    else:
        returned_db_id = insert_candidate(
            name=candidate_name,
            dimensions=scores,
            usernames=u_save,
            original_role=original_role,
            fit_direction=scores.get("fit_direction", ""),
            whats_changed_summary=scores.get("whats_changed_summary", ""),
            re_engage_flag=scores.get("re_engage_flag", False),
            status=scores.get("status", "")
        )
        print(f"  ✓ Saved to database with new id {returned_db_id}")

    # 5. Search for lifestyle social media
    lifestyle_socials = search_lifestyle_socials(candidate_name, requirements)

    return {
        "candidate_name": candidate_name,
        "rescoring_score": rescoring_score,
        "scores": scores,
        "sources": sources,
        "db_id": returned_db_id,
        "scoring_failed": scoring_failed,
        "lifestyle_socials": lifestyle_socials
    }


# ──────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("   HIRE SYSTEM — AI CANDIDATE EVALUATOR")
    print("=" * 60)

    backend = input("\nBackend to use [openrouter/ollama] (default: openrouter): ").strip().lower()
    if backend not in ("openrouter", "ollama"):
        backend = "openrouter"

    name = input("\nCandidate full name: ").strip()
    if not name:
        sys.exit("❌ Name required.")

    print("\nJob requirements (blank line to finish):\n")
    requirements = []
    while True:
        line = input(f"  Req {len(requirements)+1}: ").strip()
        if not line:
            if requirements:
                break
        else:
            requirements.append(line)

    result = evaluate_candidate(name, requirements, backend=backend)

    # Show leaderboard
    print(f"\n{'═'*60}")
    print("  CANDIDATE LEADERBOARD")
    print(f"{'═'*60}")
    all_c = get_all_candidates()
    for i, c in enumerate(all_c, 1):
        marker = " ◄ current" if c["name"] == name else ""
        print(f"  {i}. {c['name']:<30} role_domain_relevance={c['role_domain_relevance']:>3}/100{marker}")
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

# Ensure Windows terminal encoding errors never crash print statements
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

# ── Import siblings ──────────────────────────────────────
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_BACKEND, "database"))
sys.path.insert(0, os.path.join(_BACKEND, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import insert_candidate, get_all_candidates

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
# Role domain relevance is the primary differentiator
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

SCORING_SYSTEM_PROMPT = """
You are an expert AI hiring evaluator. You will receive a candidate's public profile data
collected from GitHub, LinkedIn, Google Scholar, ResearchGate, Kaggle, Dev.to, Medium,
and Hashnode, along with the job requirements.

Evaluate the candidate across exactly these 9 dimensions and return ONLY a JSON object.
No preamble, no markdown, no explanation — raw JSON only.

Dimensions (score each 0–100):
1. technical_competency    - Skills, languages, tools evident in repos/articles/projects
2. problem_solving         - Complexity of projects, Kaggle competitions, research depth
3. communication           - Quality of writing (articles, README, paper abstracts, bio)
4. career_stability        - Consistent activity, no long unexplained gaps
5. company_exposure        - Quality/prestige of orgs mentioned (GitHub org, Scholar affiliation)
6. academic_signal         - Publications, citations, FYP papers, Google Scholar presence
7. initiative              - Side projects, open source contributions, blogging, competitions
8. risk_indicators         - Gaps, inconsistencies, very low activity, no public presence (higher = more risk)
9. role_domain_relevance   - How closely the candidate's actual work matches the JD requirements (PRIMARY)

Response format (strict JSON, no extras):
{
  "technical_competency": <int 0-100>,
  "problem_solving": <int 0-100>,
  "communication": <int 0-100>,
  "career_stability": <int 0-100>,
  "company_exposure": <int 0-100>,
  "academic_signal": <int 0-100>,
  "initiative": <int 0-100>,
  "risk_indicators": <int 0-100>,
  "role_domain_relevance": <int 0-100>,
  "reasoning": {
    "technical_competency": "<one sentence>",
    "problem_solving": "<one sentence>",
    "communication": "<one sentence>",
    "career_stability": "<one sentence>",
    "company_exposure": "<one sentence>",
    "academic_signal": "<one sentence>",
    "initiative": "<one sentence>",
    "risk_indicators": "<one sentence>",
    "role_domain_relevance": "<one sentence>"
  }
}
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
                 sources: dict, kws: list[str]) -> str:

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

JOB REQUIREMENTS:
{chr(10).join(f"- {r}" for r in requirements)}

EXTRACTED KEYWORDS: {kws}

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

Based on all the above, score this candidate across the 9 dimensions.
Remember: role_domain_relevance is the PRIMARY signal.
Return ONLY the JSON object as specified.
"""
    return prompt.strip()


# ──────────────────────────────────────────────────────────
# STEP 3a: Call OpenRouter for scoring
# ──────────────────────────────────────────────────────────
def call_openrouter(prompt: str) -> dict:
    print(f"\n{'═'*60}")
    print(f"  STEP 2 — Sending to OpenRouter ({OPENROUTER_MODEL}) for scoring")
    print(f"{'═'*60}")

    if not OPENROUTER_API_KEY:
        print("  ⚠ OPENROUTER_API_KEY is not set in .env")
        return {}

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1000,
    }

    raw = ""  # pre-declare so the except handler never sees an unbound name
    try:
        r = requests.post(
            OPENROUTER_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            },
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        raw = data["choices"][0]["message"]["content"]

        # Strip markdown fences if present
        raw = re.sub(r"```json|```", "", raw).strip()
        scores = json.loads(raw)
        return scores

    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parse error: {e}")
        print(f"  Raw response: {raw[:300]}")
        return {}
    except Exception as e:
        print(f"  ⚠ OpenRouter API error: {e}")
        return {}


# ──────────────────────────────────────────────────────────
# STEP 3b: Call local Ollama for scoring
# ──────────────────────────────────────────────────────────
def call_ollama(prompt: str) -> dict:
    print(f"\n{'═'*60}")
    print(f"  STEP 2 — Sending to local Ollama ({OLLAMA_MODEL}) for scoring")
    print(f"{'═'*60}")

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    raw = ""  # pre-declare so the except handler never sees an unbound name
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()

        raw = data.get("message", {}).get("content", "")

        # Strip markdown fences if present
        raw = re.sub(r"```json|```", "", raw).strip()
        scores = json.loads(raw)
        return scores

    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parse error: {e}")
        print(f"  Raw response: {raw[:300]}")
        return {}
    except requests.exceptions.ConnectionError:
        print(f"  ⚠ Could not connect to Ollama at {OLLAMA_BASE_URL}")
        print(f"    Make sure Ollama is running locally (`ollama serve`) and the model is pulled")
        print(f"    (`ollama pull {OLLAMA_MODEL}`).")
        return {}
    except Exception as e:
        print(f"  ⚠ Ollama API error: {e}")
        return {}


# ──────────────────────────────────────────────────────────
# STEP 4: Compute weighted rescoring score
# ──────────────────────────────────────────────────────────
def compute_rescoring_score(scores: dict) -> float:
    """
    Weighted sum across 9 dimensions.
    risk_indicators is subtracted (higher risk = lower score).
    Returns a 0–100 float.
    """
    total = 0.0
    for dim, weight in WEIGHTS.items():
        val = scores.get(dim, 0)
        total += val * abs(weight) * (1 if weight > 0 else -1)

    # Normalise to 0–100
    score = max(0.0, min(100.0, total))
    return round(score, 2)


# ──────────────────────────────────────────────────────────
# STEP 5: Print report + save to DB
# ──────────────────────────────────────────────────────────
def print_and_save(candidate_name: str, scores: dict,
                   rescoring_score: float, requirements: list[str],
                   usernames: dict | None = None):

    print(f"\n{'═'*60}")
    print(f"  STEP 3 — Results for: {candidate_name}")
    print(f"{'═'*60}")

    DIM_LABELS = {
        "technical_competency":  "Technical Competency",
        "problem_solving":       "Problem Solving",
        "communication":         "Communication",
        "career_stability":      "Career Stability",
        "company_exposure":      "Company Exposure",
        "academic_signal":       "Academic Signal",
        "initiative":            "Initiative",
        "risk_indicators":       "Risk Indicators  (–)",
        "role_domain_relevance": "Role Domain Relevance  ★",
    }

    reasoning = scores.get("reasoning", {})
    for key, label in DIM_LABELS.items():
        val    = scores.get(key, "N/A")
        reason = reasoning.get(key, "")
        bar    = "█" * int((val or 0) // 10) if isinstance(val, (int, float)) else ""
        print(f"\n  {label:<35} {str(val):>3}/100  {bar}")
        if reason:
            print(f"    └ {reason}")

    print(f"\n{'─'*60}")
    print(f"  ⭐ RESCORING SCORE  :  {rescoring_score} / 100")
    print(f"{'─'*60}")

    # Save to DB — store the raw 9 dimension scores + source usernames.
    # (rescoring_score is still returned to the caller, but it's a computed
    # value now, not persisted as its own column — see Backend/database/db.py)
    dimensions = {k: scores.get(k, 0) for k in DIMENSION_KEYS}
    row_id = insert_candidate(candidate_name, dimensions, usernames)
    print(f"\n  ✅ Saved to DB  →  id={row_id}, name='{candidate_name}', "
          f"rescoring_score={rescoring_score} (computed, not stored)")

    return row_id


# ──────────────────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────────────────
def evaluate_candidate(candidate_name: str, requirements: list[str],
                       backend: str = "openrouter",
                       usernames: dict | None = None) -> dict:
    """
    backend: "openrouter" or "ollama"
    usernames: optional dict of source usernames, e.g.
        {"github_username": "torvalds", "linkedin_username": "linus-torvalds"}
        Saved to the DB alongside the candidate and now also forwarded to
        the individual platform searchers so that an exact handle is used
        instead of guessing from the candidate's full name.
    """
    # 1. Collect (pass usernames so search_* functions can use them directly)
    sources, kws = collect_candidate_data(candidate_name, requirements, usernames)

    # 2. Build prompt
    prompt = build_prompt(candidate_name, requirements, sources, kws)

    # 3. Score via chosen backend
    if backend == "ollama":
        scores = call_ollama(prompt)
    elif backend == "openrouter":
        scores = call_openrouter(prompt)
    else:
        print(f"  ❌ Unknown backend '{backend}'. Use 'openrouter' or 'ollama'.")
        return {}

    if not scores:
        # AI scoring failed — still return the collected source data
        # so the frontend can show the analytics dashboard.
        print("  ⚠ Scoring failed — returning collected data without AI scores.")
        zero_scores = {k: 0 for k in DIMENSION_KEYS}
        zero_scores["reasoning"] = {}
        return {
            "candidate":      candidate_name,
            "scores":         zero_scores,
            "rescoring_score": 0.0,
            "sources":        sources,
            "db_id":          -1,          # not saved to DB
            "backend":        backend,
            "scoring_failed": True,
        }

    # 4. Weighted total
    rescoring_score = compute_rescoring_score(scores)

    # 5. Print + save
    row_id = print_and_save(candidate_name, scores, rescoring_score,
                            requirements, usernames)

    return {
        "candidate":       candidate_name,
        "scores":          scores,
        "rescoring_score": rescoring_score,
        "sources":         sources,
        "db_id":           row_id,
        "backend":         backend,
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
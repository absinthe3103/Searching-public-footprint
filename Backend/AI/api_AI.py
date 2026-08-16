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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
sys.path.insert(0, _BACKEND)
sys.path.insert(0, os.path.join(_BACKEND, "database"))
sys.path.insert(0, os.path.join(_BACKEND, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.db import insert_candidate, get_all_candidates, CULTURE_DIMENSIONS

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

    # Culture fit — only meaningful when a summary_profile was supplied.
    # List of CULTURE_DIMENSIONS keys (from Backend/database/db.py) that best
    # describe the candidate based on their summary_profile paragraph.
    # Return an empty list if no summary_profile was given.
    culture_fit_dimensions: list[str] = Field(
        default_factory=list,
        description=(
            "Subset of these exact keys that fit the candidate's summary_profile: "
            + ", ".join(CULTURE_DIMENSIONS)
            + ". Empty list if no summary_profile was provided."
        )
    )
    
    # Enrichment Fields
    fit_direction: str = Field(description="improved, declined, or unchanged")
    whats_changed_summary: str = Field(description="A plain-language explanation of what changed in their public footprint")
    re_engage_flag: bool = Field(description="True if it is a good time to re-engage, False otherwise")
    status: str = Field(description="One of: 'Active opportunity', 'Re-engage', 'Watch', 'Faded'")
    executive_summary: str = Field(description="Markdown formatted executive summary report")

SCORING_SYSTEM_PROMPT = """
You are the HINT Master Persona, an expert AI hiring evaluator. You will receive a candidate's public profile data
collected from GitHub, LinkedIn, Google Scholar, ResearchGate, Kaggle, Dev.to, Medium,
and Hashnode, along with the job requirements and their original role/tier.

Evaluate the candidate across exactly the 9 dimensions (score 0-100).
Role domain relevance is the PRIMARY signal.

Additionally, provide candidate re-scoring (fit_direction, whats_changed_summary, re_engage_flag) 
and determine their talent radar status (Active opportunity, Re-engage, Watch, Faded) based on their signals.

If a SUMMARY PROFILE paragraph is provided, read it and select every organizational
culture dimension (from the fixed list of 7) that the paragraph reflects — a
candidate can match multiple dimensions. Base this only on what the paragraph
actually says; do not infer culture fit from GitHub/LinkedIn data. If no
summary profile is provided, return an empty list for culture_fit_dimensions.

Generate a comprehensive, professional Executive Summary Report for the hiring manager.
Your tone should be objective, highly analytical, and decisive.
Generate the report in clean Markdown format using the following structure:
### 1. Executive Pitch
Provide a concise 2-3 sentence high-level pitch of the candidate. Who are they, what is their core expertise, and what is their estimated seniority level (e.g., Junior, Mid-level, Senior)?
### 2. Education & Academic Signals
Summarize their educational background (e.g., University, degrees). Highlight notable academic signals.
### 3. Top Projects & Public Footprint
Highlight the top 2-3 most impressive public contributions.
### 4. Job Alignment & Skill Matrix
Evaluate how closely their public footprint aligns with the specific Job Requirements.
### 5. Cultural Fit & Behavioral Indicators
Infer their working style based on public footprint.
### 6. Risk Assessment & Blind Spots
Identify any potential red flags or missing signals.
### 7. Hiring Recommendation
Provide a definitive recommendation from: STRONG YES (Fast Track), YES (Proceed to Interview), WATCH (Keep in Pipeline), PASS (Does not meet bar). Provide a 1-2 sentence justification.
"""


# ──────────────────────────────────────────────────────────
# STEP 1: Collect candidate data via searcher
# ──────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────
# ROLE → PLATFORM MAPPING
# ──────────────────────────────────────────────────────────
ROLE_PLATFORM_MAP: dict[str, list[tuple[str, str, str | None]]] = {
    "it": [
        ("github",         "search_github",         "github_username"),
        ("linkedin",       "search_linkedin",        "linkedin_username"),
        ("google_scholar", "search_google_scholar",  "google_scholar_identifier"),
        ("researchgate",   "search_researchgate",    "researchgate_identifier"),
        ("kaggle",         "search_kaggle",          "kaggle_username"),
        ("devto",          "search_devto",           "devto_username"),
        ("medium",         "search_medium",          "medium_username"),
        ("hashnode",       "search_hashnode",        "hashnode_username"),
    ],
    "marketing": [
        ("linkedin",        "search_linkedin",        "linkedin_username"),
        ("instagram",       "search_instagram",       "instagram_username"),
        ("tiktok",          "search_tiktok",          "tiktok_username"),
        ("meta_ad_library", "search_meta_ad_library", "meta_ad_page"),
        ("similarweb",      "search_similarweb",      "similarweb_domain"),
        ("medium",          "search_medium",          "medium_username"),
    ],
    "hr": [
        ("linkedin",  "search_linkedin",          "linkedin_username"),
        ("shrm",      "search_shrm",              "shrm_identifier"),
        ("cipd",      "search_cipd",              "cipd_identifier"),
        ("glassdoor", "search_glassdoor_employer", "glassdoor_employer"),
        ("ssm_acra",  "search_ssm_acra",          "company_identifier"),
        ("medium",    "search_medium",            "medium_username"),
    ],
    "design": [
        ("linkedin",  "search_linkedin",  "linkedin_username"),
        ("behance",   "search_behance",   "behance_username"),
        ("dribbble",  "search_dribbble",  "dribbble_username"),
        ("github",    "search_github",    "github_username"),
        ("medium",    "search_medium",    "medium_username"),
    ],
    "finance": [
        ("linkedin",  "search_linkedin",          "linkedin_username"),
        ("google_scholar", "search_google_scholar","google_scholar_identifier"),
        ("sc_mq",     "search_sc_mq",             "finance_license_identifier"),
        ("glassdoor", "search_glassdoor_employer", "glassdoor_employer"),
        ("ssm_acra",  "search_ssm_acra",          "company_identifier"),
    ],
    "research": [
        ("linkedin",       "search_linkedin",        "linkedin_username"),
        ("google_scholar", "search_google_scholar",  "google_scholar_identifier"),
        ("researchgate",   "search_researchgate",    "researchgate_identifier"),
        ("github",         "search_github",          "github_username"),
        ("medium",         "search_medium",          "medium_username"),
    ],
}

ROLE_KEYWORDS: dict[str, list[str]] = {
    "marketing": ["marketing","social media","instagram","tiktok","facebook","brand","campaign","content","influencer","ads","digital marketing","seo","sem","growth","engagement"],
    "hr":        ["hr","human resource","recruitment","talent","payroll","cipd","shrm","people operations","training","organisational","labor","labour","hris"],
    "design":    ["design","ui","ux","graphic","figma","sketch","adobe","creative","visual","motion","branding","product design"],
    "finance":   ["finance","accounting","audit","cfa","acca","investment","banking","risk","compliance","treasury","financial planning"],
    "research":  ["research","phd","academia","publication","journal","ieee","acm","scholar","laboratory","experiment"],
    "it":        ["software","engineering","developer","python","java","react","cloud","devops","backend","frontend","fullstack","data science","machine learning","ai","cybersecurity","network","system","aws","node"],
}


def detect_role_domain(original_role: str, requirements: list[str]) -> str:
    """
    Returns the role domain key by scoring role string and requirements.
    original_role is weighted 3x heavier than requirements so an explicit
    role title (e.g. "HR") always wins over incidental skill keywords (e.g. React).
    Defaults to 'it' if no clear match.
    """
    role_text = original_role.lower()
    req_text  = " ".join(requirements).lower()

    scores = {domain: 0 for domain in ROLE_KEYWORDS}
    for domain, kws in ROLE_KEYWORDS.items():
        for kw in kws:
            if kw in role_text:
                scores[domain] += 3   # role title — high weight
            if kw in req_text:
                scores[domain] += 1   # requirement — low weight

    best = max(scores, key=scores.get)
    best_score = scores[best]
    if best_score == 0:
        return "it"
    print(f"  Role detected: '{best}' (score={best_score})")
    return best


def collect_candidate_data(candidate_name: str, requirements: list[str],
                           usernames: dict | None = None,
                           original_role: str = "") -> tuple[dict, list]:
    """
    Collect public profile data. Platforms are selected based on detected role domain:
      IT        → GitHub, LinkedIn, Scholar, Kaggle, Dev.to, Medium, Hashnode
      Marketing → LinkedIn, Instagram, TikTok, Meta Ad Library, Similarweb, Medium
      HR        → LinkedIn, SHRM, CIPD, Glassdoor, SSM/ACRA, Medium
      Design    → LinkedIn, Behance, Dribbble, GitHub, Medium
      Finance   → LinkedIn, Scholar, SC/MQ, Glassdoor, SSM/ACRA
      Research  → LinkedIn, Scholar, ResearchGate, GitHub, Medium
    """
    print(f"\n{'='*60}")
    print(f"  STEP 1 — Collecting public profile data")
    print(f"{'='*60}")

    from candidateSearcher import (
        search_github, search_linkedin, search_google_scholar,
        search_researchgate, search_kaggle, search_devto,
        search_medium, search_hashnode,
        search_instagram, search_tiktok, search_meta_ad_library, search_similarweb,
        search_shrm, search_cipd, search_glassdoor_employer, search_ssm_acra,
        search_behance, search_dribbble, search_sc_mq,
        STOP
    )

    fn_registry = {
        "search_github": search_github, "search_linkedin": search_linkedin,
        "search_google_scholar": search_google_scholar, "search_researchgate": search_researchgate,
        "search_kaggle": search_kaggle, "search_devto": search_devto,
        "search_medium": search_medium, "search_hashnode": search_hashnode,
        "search_instagram": search_instagram, "search_tiktok": search_tiktok,
        "search_meta_ad_library": search_meta_ad_library, "search_similarweb": search_similarweb,
        "search_shrm": search_shrm, "search_cipd": search_cipd,
        "search_glassdoor_employer": search_glassdoor_employer, "search_ssm_acra": search_ssm_acra,
        "search_behance": search_behance, "search_dribbble": search_dribbble,
        "search_sc_mq": search_sc_mq,
    }

    kws = []
    for req in requirements:
        for w in re.split(r"[\s,/+()\.\-]+", req.lower()):
            if w and w not in STOP and len(w) > 2:
                kws.append(w)
    kws = list(dict.fromkeys(kws))
    print(f"  Keywords: {kws}\n")

    u = usernames or {}
    role_domain  = detect_role_domain(original_role, requirements)
    platform_spec = ROLE_PLATFORM_MAP.get(role_domain, ROLE_PLATFORM_MAP["it"])
    print(f"  Platforms for '{role_domain}': {[p[0] for p in platform_spec]}\n")

    platform_tasks: dict[str, tuple] = {}
    for source_key, fn_name, username_key in platform_spec:
        fn = fn_registry.get(fn_name)
        if fn is None:
            print(f"  ⚠ No function for '{fn_name}' — skipping")
            continue
        identifier = u.get(username_key) if username_key else None
        platform_tasks[source_key] = (fn, candidate_name, kws, identifier)

    sources: dict = {}
    with ThreadPoolExecutor(max_workers=max(1, len(platform_tasks))) as executor:
        future_to_platform = {
            executor.submit(fn, *args): source_key
            for source_key, (fn, *args) in platform_tasks.items()
        }
        for future in as_completed(future_to_platform):
            source_key = future_to_platform[future]
            try:
                sources[source_key] = future.result()
            except Exception as exc:
                print(f"  ⚠ [{source_key}] exception: {exc}")
                sources[source_key] = {"summary": f"Error: {exc}", "profile_url": None, "keyword_hits": {}}

    return sources, kws


def build_prompt(candidate_name: str, requirements: list[str],
                 sources: dict, kws: list[str], 
                 original_role: str = "", original_tier: str = "",
                 university: str = "", summary_profile: str = "") -> str:

    rubric_block = ""
    try:
        rubrics_path = os.path.join(os.path.dirname(__file__), "rubrics.json")
        with open(rubrics_path, "r", encoding="utf-8") as f:
            rubrics_data = json.load(f)
            
        role_rubric = None
        for sector, roles in rubrics_data.get("rubric", {}).items():
            if original_role in roles:
                role_rubric = roles[original_role]
                break
                
        if role_rubric:
            rubric_block = f"\nEVALUATION RUBRIC FOR '{original_role}':\n" + json.dumps(role_rubric, indent=2) + "\n"
        else:
            scoring_bands = rubrics_data.get("_meta", {}).get("scoring_bands", {})
            rubric_block = f"\nSCORING BANDS:\n" + json.dumps(scoring_bands, indent=2) + "\n"
    except Exception as e:
        print(f"  ⚠ Could not load rubrics.json: {e}")

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

    summary_profile_block = (
        f"\nSUMMARY PROFILE (candidate-provided):\n{summary_profile}\n"
        if summary_profile else
        "\nSUMMARY PROFILE: Not provided — return an empty list for culture_fit_dimensions.\n"
    )

    prompt = f"""
CANDIDATE: {candidate_name}
ORIGINAL ROLE: {original_role or 'Unknown'}
ORIGINAL TIER: {original_tier or 'Unknown'}
UNIVERSITY: {university or 'Unknown'}
{summary_profile_block}
JOB REQUIREMENTS:
{chr(10).join(f"- {r}" for r in requirements)}
{rubric_block}
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
        print(f"  ⚠ Gemini API error: {e}")
        return {}


def call_openrouter(prompt: str) -> dict:
    """
    Send prompt to OpenRouter API — access to 100+ models (DeepSeek, Claude, GPT-4o, etc.)
    Configure via .env:
        OPENROUTER_API_KEY=your_key_here
        OPENROUTER_MODEL=deepseek/deepseek-v4-flash
    Browse models: https://openrouter.ai/models
    """
    print(f"\n{'='*60}")
    print(f"  STEP 2 — Sending to OpenRouter ({OPENROUTER_MODEL}) for scoring")
    print(f"{'='*60}")

    if not OPENROUTER_API_KEY:
        print("  ⚠ OPENROUTER_API_KEY is not set in .env")
        return {}

    payload = {
        "model": OPENROUTER_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt + """

IMPORTANT: You MUST respond with ONLY a valid JSON object matching this exact structure (no extra text, no markdown):
{
  "technical_competency": <integer 0-100>,
  "problem_solving": <integer 0-100>,
  "communication": <integer 0-100>,
  "career_stability": <integer 0-100>,
  "company_exposure": <integer 0-100>,
  "academic_signal": <integer 0-100>,
  "initiative": <integer 0-100>,
  "risk_indicators": <integer 0-100>,
  "role_domain_relevance": <integer 0-100>,
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
  },
  "fit_direction": "<improved|declined|unchanged>",
  "whats_changed_summary": "<plain English summary>",
  "re_engage_flag": <true|false>,
  "status": "<Active opportunity|Re-engage|Watch|Faded>",
  "executive_summary": "<Markdown string>",
  "culture_fit_dimensions": []
}"""},
        ],
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://hiresystem.local",
        "X-Title":       "HireSystem",
    }
    try:
        r = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=120)
        r.raise_for_status()
        data = r.json()
        raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not raw_text:
            print("  ⚠ OpenRouter returned empty content")
            return {}
        cleaned = re.sub(r"```(?:json)?\s*|```", "", raw_text).strip()
        return json.loads(cleaned)
    except requests.exceptions.ConnectionError:
        print("  ⚠ Cannot connect to OpenRouter — check your internet")
        return {}
    except requests.exceptions.Timeout:
        print("  ⚠ OpenRouter request timed out")
        return {}
    except requests.exceptions.HTTPError as e:
        sc = r.status_code
        if sc == 401: print("  ⚠ OpenRouter: Invalid API key")
        elif sc == 402: print("  ⚠ OpenRouter: Insufficient credits")
        elif sc == 429: print("  ⚠ OpenRouter: Rate limited — try again shortly")
        else: print(f"  ⚠ OpenRouter HTTP error: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"  ⚠ OpenRouter response not valid JSON: {e}")
        return {}
    except Exception as e:
        print(f"  ⚠ OpenRouter error: {e}")
        return {}


def call_ollama(prompt: str) -> dict:
    """
    Send prompt to a local Ollama instance.
    Ollama must be running: ollama serve
    Model must be pulled:   ollama pull <model>
    Configure via .env:
        OLLAMA_BASE_URL=http://localhost:11434
        OLLAMA_MODEL=qwen2.5:14b
    """
    print(f"\n{'='*60}")
    print(f"  STEP 2 — Sending to Ollama ({OLLAMA_MODEL}) for scoring")
    print(f"{'='*60}")

    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 8192,
            "num_ctx": 16384,
        },
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt + """

IMPORTANT: You MUST respond with ONLY a valid JSON object matching this exact structure (no extra text, no markdown):
{
  "technical_competency": <integer 0-100>,
  "problem_solving": <integer 0-100>,
  "communication": <integer 0-100>,
  "career_stability": <integer 0-100>,
  "company_exposure": <integer 0-100>,
  "academic_signal": <integer 0-100>,
  "initiative": <integer 0-100>,
  "risk_indicators": <integer 0-100>,
  "role_domain_relevance": <integer 0-100>,
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
  },
  "fit_direction": "<improved|declined|unchanged>",
  "whats_changed_summary": "<plain English summary>",
  "re_engage_flag": <true|false>,
  "status": "<Active opportunity|Re-engage|Watch|Faded>",
  "executive_summary": "<Markdown string>",
  "culture_fit_dimensions": []
}"""},
        ],
    }
    try:
        r = requests.post(url, json=payload, timeout=600)
        r.raise_for_status()
        data = r.json()
        raw_text = data.get("message", {}).get("content", "")
        print(f"  [Ollama] Response length: {len(raw_text)} chars")
        if raw_text:
            print(f"  [Ollama] First 300 chars: {raw_text[:300]}")
        if not raw_text:
            print("  ⚠ Ollama returned empty content")
            print(f"  [Ollama] Full response keys: {list(data.keys())}")
            return {}
        cleaned = re.sub(r"```(?:json)?\s*|```", "", raw_text).strip()
        return json.loads(cleaned)
    except requests.exceptions.ConnectionError:
        print(f"  ⚠ Cannot connect to Ollama at {OLLAMA_BASE_URL}")
        print("    Make sure Ollama is running: ollama serve")
        return {}
    except requests.exceptions.Timeout:
        print("  ⚠ Ollama request timed out (model may be slow)")
        return {}
    except json.JSONDecodeError as e:
        print(f"  ⚠ Ollama response not valid JSON: {e}")
        return {}
    except Exception as e:
        print(f"  ⚠ Ollama error: {e}")
        return {}


def evaluate_candidate(candidate_name: str, requirements: list[str],
                       backend: str = "gemini",
                       usernames: dict | None = None,
                       original_role: str = "", original_tier: str = "",
                       university: str = "", summary_profile: str = "") -> dict | None:
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
    sources, kws = collect_candidate_data(candidate_name, requirements, usernames, original_role=original_role)
    if not any(sources.values()):
        print("⚠ No profiles found across any platform. Aborting.")
        return None

    # 2. Build prompt
    prompt = build_prompt(candidate_name, requirements, sources, kws,
                          original_role, original_tier, university, summary_profile)

    # 3. Route to correct AI backend
    if backend == "ollama":
        scores = call_ollama(prompt)
    elif backend == "openrouter":
        scores = call_openrouter(prompt)
    elif backend == "gemini":
        scores = call_gemini(prompt)
    else:
        print(f"  ⚠ Unknown backend '{backend}', falling back to gemini")
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
        scores["executive_summary"] = "AI evaluation failed"
        scores["culture_fit_dimensions"] = []
        scoring_failed = True

    # 4. Compute final rescoring score
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

    # 5. Extract usernames and save to DB
    u_save = {
        "github_username":   sources.get("github", {}).get("username"),
        "linkedin_username": sources.get("linkedin", {}).get("username"),
        "kaggle_username":   sources.get("kaggle", {}).get("username"),
        "devto_username":    sources.get("devto", {}).get("username"),
        "medium_username":   sources.get("medium", {}).get("username"),
        "hashnode_username": sources.get("hashnode", {}).get("username"),
    }

    db_id = insert_candidate(
        name=candidate_name,
        dimensions=scores,
        usernames=u_save,
        original_role=original_role,
        original_tier=original_tier,
        university=university,
        summary_profile=summary_profile,
        culture_fit_dimensions=[
            d for d in scores.get("culture_fit_dimensions", []) if d in CULTURE_DIMENSIONS
        ],
        fit_direction=scores.get("fit_direction", ""),
        whats_changed_summary=scores.get("whats_changed_summary", ""),
        re_engage_flag=scores.get("re_engage_flag", False),
        status=scores.get("status", ""),
        executive_summary=scores.get("executive_summary", "")
    )
    print(f"  ✓ Saved to database with ID {db_id}")

    return {
        "candidate_name": candidate_name,
        "rescoring_score": rescoring_score,
        "scores": scores,
        "sources": sources,
        "db_id": db_id,
        "scoring_failed": scoring_failed,
    }


# ──────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("   HIRE SYSTEM — AI CANDIDATE EVALUATOR")
    print("=" * 60)

    backend = input("\nBackend to use [gemini/openrouter/ollama] (default: gemini): ").strip().lower()
    if backend not in ("gemini", "openrouter", "ollama"):
        backend = "gemini"

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
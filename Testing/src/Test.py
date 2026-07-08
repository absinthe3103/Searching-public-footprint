"""
test_hire_system.py

Standalone test/comparison harness for the HIRE SYSTEM FastAPI backend (logic.py).

What it does:
  1. Health-checks the running API (GET /)
  2. Runs the SAME candidate through BOTH backends — OpenRouter and local Ollama —
     via POST /evaluate, so you can compare scoring quality/consistency.
  3. Prints a side-by-side comparison of the 9 dimensions + rescoring score.
  4. Sanity-checks GET /candidates and GET /candidates/{id}.

Requirements:
  pip install requests

Usage:
  1. Start the API in one terminal:
       uvicorn logic:app --reload --port 8000
  2. (Optional, for the ollama leg) start Ollama in another terminal:
       ollama serve
       ollama pull llama3.1
  3. Run this script in a third terminal:
       python test_hire_system.py
       python test_hire_system.py --backend openrouter   # only test one backend
       python test_hire_system.py --backend ollama
       python test_hire_system.py --name "Andrew Ng" --req "Machine Learning" --req "Python"
"""

import argparse
import sys
import time

import requests

API_BASE = "http://127.0.0.1:8000"

DEFAULT_CANDIDATE = "Andrew Ng"
DEFAULT_REQUIREMENTS = [
    "Machine Learning",
    "Python",
    "Deep Learning",
    "Published research",
]

DIM_ORDER = [
    "technical_competency", "problem_solving", "communication",
    "career_stability", "company_exposure", "academic_signal",
    "initiative", "risk_indicators", "role_domain_relevance",
]

DIM_LABELS = {
    "technical_competency":  "Technical Competency",
    "problem_solving":       "Problem Solving",
    "communication":         "Communication",
    "career_stability":      "Career Stability",
    "company_exposure":      "Company Exposure",
    "academic_signal":       "Academic Signal",
    "initiative":            "Initiative",
    "risk_indicators":       "Risk Indicators (-)",
    "role_domain_relevance": "Role Domain Relevance *",
}


def hr(char="─", width=60):
    print(char * width)


def check_health() -> bool:
    print("\n" + "=" * 60)
    print("  HEALTH CHECK — GET /")
    print("=" * 60)
    try:
        r = requests.get(f"{API_BASE}/", timeout=5)
        r.raise_for_status()
        print(f"  ✅ API is up: {r.json()}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Could not reach {API_BASE}")
        print("     Is the server running? Try: uvicorn logic:app --reload --port 8000")
        return False
    except Exception as e:
        print(f"  ❌ Health check failed: {e}")
        return False


def run_evaluate(candidate_name: str, requirements: list, backend: str, timeout: int = 120):
    print(f"\n{'═'*60}")
    print(f"  POST /evaluate   backend={backend}   candidate={candidate_name}")
    print(f"{'═'*60}")

    payload = {
        "candidate_name":   candidate_name,
        "job_requirements": requirements,
        "backend":          backend,
    }

    start = time.time()
    try:
        r = requests.post(f"{API_BASE}/evaluate", json=payload, timeout=timeout)
        elapsed = round(time.time() - start, 1)

        if r.status_code != 200:
            print(f"  ❌ HTTP {r.status_code} ({elapsed}s): {r.text[:400]}")
            return None

        data = r.json()
        print(f"  ✅ Success in {elapsed}s — score: {data['rescoring_score']}/100")
        return data

    except requests.exceptions.ConnectionError:
        print(f"  ❌ Could not reach {API_BASE}")
        return None
    except requests.exceptions.Timeout:
        print(f"  ❌ Request timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return None


def print_comparison(results: dict):
    """
    results: { "openrouter": <response dict or None>, "ollama": <response dict or None> }
    """
    print(f"\n{'═'*60}")
    print("  SIDE-BY-SIDE COMPARISON")
    print(f"{'═'*60}")

    backends = [b for b in ("openrouter", "ollama") if results.get(b)]
    if not backends:
        print("  ⚠ No successful results to compare.")
        return

    header = f"  {'Dimension':<28}" + "".join(f"{b.upper():>15}" for b in backends)
    print(header)
    hr(width=len(header))

    for dim in DIM_ORDER:
        row = f"  {DIM_LABELS[dim]:<28}"
        for b in backends:
            val = results[b]["dimensions"].get(dim, "N/A")
            row += f"{str(val):>15}"
        print(row)

    hr(width=len(header))
    row = f"  {'RESCORING SCORE':<28}"
    for b in backends:
        row += f"{str(results[b]['rescoring_score']):>15}"
    print(row)

    if len(backends) == 2:
        diff = abs(results[backends[0]]["rescoring_score"] - results[backends[1]]["rescoring_score"])
        print(f"\n  Δ Score difference between backends: {round(diff, 2)} points")


def check_candidates_list():
    print(f"\n{'═'*60}")
    print("  GET /candidates")
    print(f"{'═'*60}")
    try:
        r = requests.get(f"{API_BASE}/candidates", timeout=10)
        r.raise_for_status()
        rows = r.json()
        print(f"  ✅ {len(rows)} candidate(s) in DB")
        for row in rows[:10]:
            print(f"     id={row['id']:<4} {row['name']:<25} {row['rescoring_score']:>6}/100")
        return rows
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return []


def check_candidate_by_id(candidate_id: int):
    print(f"\n{'═'*60}")
    print(f"  GET /candidates/{candidate_id}")
    print(f"{'═'*60}")
    try:
        r = requests.get(f"{API_BASE}/candidates/{candidate_id}", timeout=10)
        if r.status_code == 404:
            print(f"  ⚠ Candidate id={candidate_id} not found (expected if DB is empty).")
            return None
        r.raise_for_status()
        print(f"  ✅ {r.json()}")
        return r.json()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test/compare the HIRE SYSTEM API across backends.")
    parser.add_argument("--backend", choices=["openrouter", "ollama", "both"], default="both",
                        help="Which backend(s) to test (default: both)")
    parser.add_argument("--name", default=DEFAULT_CANDIDATE, help="Candidate full name")
    parser.add_argument("--req", action="append", dest="requirements",
                        help="Job requirement (repeatable). If omitted, uses default sample requirements.")
    parser.add_argument("--base-url", default=API_BASE, help="API base URL (default: http://127.0.0.1:8000)")
    args = parser.parse_args()

    globals()["API_BASE"] = args.base_url.rstrip("/")

    requirements = args.requirements or DEFAULT_REQUIREMENTS

    print("=" * 60)
    print("   HIRE SYSTEM — API TEST HARNESS")
    print("=" * 60)
    print(f"  Target:      {API_BASE}")
    print(f"  Candidate:   {args.name}")
    print(f"  Requirements:")
    for r in requirements:
        print(f"    - {r}")

    if not check_health():
        sys.exit(1)

    backends_to_run = ["openrouter", "ollama"] if args.backend == "both" else [args.backend]

    results = {}
    for backend in backends_to_run:
        results[backend] = run_evaluate(args.name, requirements, backend)

    if len(backends_to_run) > 1 or backends_to_run == ["openrouter", "ollama"]:
        print_comparison(results)
    elif results.get(backends_to_run[0]):
        # single backend — just show its dimensions
        data = results[backends_to_run[0]]
        print(f"\n{'─'*60}")
        for dim in DIM_ORDER:
            print(f"  {DIM_LABELS[dim]:<28} {data['dimensions'].get(dim, 'N/A')}/100")
        print(f"{'─'*60}")
        print(f"  RESCORING SCORE: {data['rescoring_score']}/100")

    rows = check_candidates_list()
    if rows:
        check_candidate_by_id(rows[0]["id"])
    else:
        check_candidate_by_id(1)

    print(f"\n{'═'*60}")
    print("  DONE")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
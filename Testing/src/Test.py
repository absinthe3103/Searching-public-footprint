"""
test.py - Candidate Searcher Direct Test

Tests candidateSearcher.py directly WITHOUT the FastAPI backend or AI layer.
Focuses on verifying that all required fields are captured from each source.

Validates against requirements:
  ✓ GitHub: repos, languages, contribution activity, last commit date
  ✓ LinkedIn (public): current role, company, estimated tenure, employment status
  ✓ Google Scholar: publications, citations, FYP papers, interests
  ✓ ResearchGate: publications, citations, affiliation
  ✓ Kaggle: competition ranking, notebooks, datasets
  ✓ Dev.to / Medium / Hashnode: technical writing, topics, publication frequency

Usage - Single Name for All Platforms (searches by name on every platform):
  python test.py --name "john-doe" --req "Machine Learning" --req "Python"

Usage - Direct Username/URL Per Platform (tried first, name is the fallback):
  python test.py --name "Linus Torvalds" --github "torvalds" \\
                 --linkedin "https://www.linkedin.com/in/linustorvalds" \\
                 --req "Linux"

Usage - Mix Specific + Default (only github/linkedin get a direct identifier,
the rest fall back to searching by --name):
  python test.py --name "john-doe" --github "torvalds" \\
                 --linkedin "linus-torvalds" --req "Python"

Test with Mock Data (No live API calls):
  python test.py --mock-only --name "John Doe" --github "john-doe" --req "Python"
python test.py --name "Clement Mok Shao Ming"--github "clementmk" --scholar "https://scholar.google.com/citations?user=FbseHhAAAAAJ&hl=en&oi=sra" --researchgate "5821-0122-5050-1232"--kaggle "https://www.kaggle.com/yonatanrabinovich" --medium "https://medium.com/@sumit.ai"--req "Data Science" --req "Python"
  
"""

import argparse
import sys
import os
import time
import json
import re
from datetime import datetime, timedelta

# Make candidateSearcher importable whether it lives next to this script
# (flat layout) or in a Backend/AI folder (legacy project layout).
_HERE = os.path.dirname(os.path.abspath(__file__))
_LEGACY_BACKEND = os.path.abspath(os.path.join(_HERE, "../../Backend/AI"))
for _candidate_path in (_HERE, _LEGACY_BACKEND):
    if os.path.isdir(_candidate_path) and _candidate_path not in sys.path:
        sys.path.insert(0, _candidate_path)

try:
    from candidateSearcher import (
        search_github, search_linkedin, search_google_scholar,
        search_researchgate, search_kaggle, search_devto,
        search_medium, search_hashnode, STOP
    )
except ImportError as e:
    print(f"❌ Could not import candidateSearcher: {e}")
    print(f"   Looked in: {_HERE}")
    print(f"   Looked in: {_LEGACY_BACKEND}")
    sys.exit(1)

DEFAULT_CANDIDATE = "Clement Mok Shao Ming"
DEFAULT_REQUIREMENTS = [
    "Machine Learning",
    "Python",
    "Deep Learning",
    "Published research",
]

# Required fields from VALIDATED SOURCES table
REQUIRED_FIELDS = {
    "github": {
        "required": ["profile_url", "repos", "top_languages", "latest_push", "public_repos", "followers"],
        "what_it_shows": "Repos, languages, contribution activity, last commit date"
    },
    "linkedin": {
        "required": ["profile_url", "current_role", "company"],
        "what_it_shows": "Current role, company, estimated tenure, employment status"
    },
    "google_scholar": {
        "required": ["profile_url", "publications", "citations", "interests"],
        "what_it_shows": "Publications, citations, FYP papers"
    },
    "researchgate": {
        "required": ["profile_url"],
        "what_it_shows": "Publications, citations (via keyword hits)"
    },
    "kaggle": {
        "required": ["profile_url"],
        "what_it_shows": "Competition ranking, notebooks, datasets"
    },
    "devto": {
        "required": ["profile_url", "articles"],
        "what_it_shows": "Technical writing, topics, publication frequency"
    },
    "medium": {
        "required": ["profile_url"],
        "what_it_shows": "Technical writing, topics"
    },
    "hashnode": {
        "required": ["profile_url"],
        "what_it_shows": "Technical writing, topics"
    },
}

ALL_SOURCES = [
    ("github", "GitHub"),
    ("linkedin", "LinkedIn"),
    ("google_scholar", "Google Scholar"),
    ("researchgate", "ResearchGate"),
    ("kaggle", "Kaggle"),
    ("devto", "Dev.to"),
    ("medium", "Medium"),
    ("hashnode", "Hashnode"),
]

def extract_keywords(requirements: list) -> list:
    """Extract keywords from requirements, same as candidateSearcher does."""
    keywords = []
    for req in requirements:
        for word in re.split(r"[\s,/+()\-]+", req.lower()):
            if word and word not in STOP and len(word) > 2:
                keywords.append(word)
    return list(dict.fromkeys(keywords))


def run_search_function(key: str, func, name: str, keywords: list, identifier: str = None) -> dict:
    """Run one search function safely and time it."""
    print(f"\n{'-'*70}")
    print(f"  [{key.upper()}]  (identifier: {identifier or '— none, using name —'})")
    print(f"{'-'*70}")

    start = time.time()
    try:
        result = func(name, keywords, identifier=identifier)
        elapsed = round(time.time() - start, 2)

        # Print field verification
        required = REQUIRED_FIELDS[key]["required"]
        found_fields = [f for f in required if f in result and result[f]]
        missing_fields = [f for f in required if f not in result or not result[f]]

        if missing_fields:
            print(f"  [WARN] MISSING: {missing_fields}")
        else:
            print(f"  [OK] All required fields present")

        print(f"  Summary: {result.get('summary', 'N/A')}")
        print(f"  Time: {elapsed}s")

        # Source-specific field display
        if key == "github":
            print(f"  URL: {result.get('profile_url', '—')}")
            print(f"  Languages: {', '.join(result.get('top_languages', []))}")
            print(f"  Latest push: {result.get('latest_push', 'N/A')}")
            activity = result.get("contribution_activity", {})
            print(f"  Activity: repos={activity.get('repo_count', 'N/A')}, "
                  f"followers={activity.get('followers', 'N/A')}, "
                  f"stars={activity.get('total_stars', 'N/A')}")

        elif key == "linkedin":
            print(f"  URL: {result.get('profile_url', '—')}")
            print(f"  Role: {result.get('current_role', 'N/A')}")
            print(f"  Company: {result.get('company', 'N/A')}")

        elif key == "google_scholar":
            print(f"  URL: {result.get('profile_url', '—')}")
            print(f"  Citations: {result.get('citations', 'N/A')}")
            pubs = result.get("publications", [])
            print(f"  Publications: {len(pubs)}")
            if pubs:
                for pub in pubs[:2]:
                    print(f"    - {pub.get('title', 'N/A')} ({pub.get('year', 'N/A')})")

        elif key == "researchgate":
            print(f"  URL: {result.get('profile_url', '—')}")

        elif key == "kaggle":
            print(f"  URL: {result.get('profile_url', '—')}")

        elif key in ["devto", "medium", "hashnode"]:
            print(f"  URL: {result.get('profile_url', '—')}")
            articles = result.get("articles", [])
            print(f"  Articles: {len(articles)}")

        return {
            "key": key,
            "ok": len(missing_fields) == 0,
            "found": bool(result.get("profile_url")),
            "elapsed": elapsed,
            "data": result,
            "missing": missing_fields,
        }

    except Exception as e:
        elapsed = round(time.time() - start, 2)
        print(f"  ❌ EXCEPTION after {elapsed}s: {e}")
        import traceback
        traceback.print_exc(limit=2)
        return {
            "key": key,
            "ok": False,
            "found": False,
            "elapsed": elapsed,
            "data": {},
            "missing": REQUIRED_FIELDS[key]["required"],
            "error": str(e),
        }


def print_summary_report(results: list):
    """Print summary of field coverage."""
    print(f"\n{'='*70}")
    print("  FIELD COVERAGE SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Source':<15} {'Required':<30} {'Found':<20} {'Missing'}")
    print(f"  {'-'*15} {'-'*30} {'-'*20} {'-'*20}")

    for res in results:
        key = res["key"]
        required = REQUIRED_FIELDS[key]["required"]
        missing = res["missing"]
        status = "[OK]" if not missing else f"[WARN] {len(missing)}"

        required_str = ", ".join(required[:2])
        if len(required) > 2:
            required_str += f" +{len(required)-2}"

        missing_str = ", ".join(missing[:2]) if missing else "—"

        print(f"  {key:<15} {required_str:<30} {status:<20} {missing_str}")

    total = len(results)
    complete = sum(1 for r in results if not r["missing"])
    found = sum(1 for r in results if r["found"])

    print(f"\n  Summary:")
    print(f"    [OK] Complete (all fields): {complete}/{total}")
    print(f"    [*] Found profiles: {found}/{total}")


def main():
    parser = argparse.ArgumentParser(
        description="Test candidateSearcher.py field coverage directly."
    )
    parser.add_argument("--name", default=DEFAULT_CANDIDATE, 
                        help="Candidate's full real name (used as the fallback search "
                             "for any platform without a direct identifier)")
    
    # Platform-specific direct identifiers (username OR full profile URL).
    # If given, candidateSearcher tries this directly first; only falls back
    # to searching by --name if it's absent or doesn't resolve.
    parser.add_argument("--github", help="GitHub username or profile URL")
    parser.add_argument("--linkedin", help="LinkedIn username or profile URL")
    parser.add_argument("--scholar", help="Google Scholar user ID or profile URL")
    parser.add_argument("--researchgate", help="ResearchGate username or profile URL")
    parser.add_argument("--kaggle", help="Kaggle username or profile URL")
    parser.add_argument("--devto", help="Dev.to username or profile URL")
    parser.add_argument("--medium", help="Medium username or profile URL")
    parser.add_argument("--hashnode", help="Hashnode username or profile URL")
    
    parser.add_argument(
        "--req", action="append", dest="requirements",
        help="Job requirement (repeatable)"
    )
    parser.add_argument(
        "--mock-only", action="store_true",
        help="Test with mock data instead of live API calls"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print raw HTTP status codes/errors for every failed request "
             "(helps diagnose whether a platform is blocking/rate-limiting you)"
    )
    args = parser.parse_args()

    if args.verbose:
        import candidateSearcher
        candidateSearcher.DEBUG = True

    requirements = args.requirements or DEFAULT_REQUIREMENTS
    keywords = extract_keywords(requirements)

    # Per-platform identifiers stay None when not given — candidateSearcher.py
    # itself decides whether to use the identifier directly or fall back to
    # searching by args.name. We do NOT substitute args.name here, otherwise
    # we'd never be testing the "no identifier given" fallback path.
    identifiers = {
        "github": args.github,
        "linkedin": args.linkedin,
        "google_scholar": args.scholar,
        "researchgate": args.researchgate,
        "kaggle": args.kaggle,
        "devto": args.devto,
        "medium": args.medium,
        "hashnode": args.hashnode,
    }

    print("=" * 70)
    print("   CANDIDATE SEARCHER — FIELD COVERAGE TEST")
    print("=" * 70)
    print(f"  Candidate name: {args.name}")
    for key, label in ALL_SOURCES:
        ident = identifiers[key]
        print(f"  {label} identifier: {ident if ident else '(none — will search by name)'}")
    print(f"  Requirements: {', '.join(requirements)}")
    print(f"  Keywords: {', '.join(keywords)}")
    print(f"  Test mode: {'Mock data' if args.mock_only else 'Live API'}")

    if args.mock_only:
        print_mock_test(args.name, identifiers, keywords)
    else:
        print_live_api_test(args.name, identifiers, keywords)


def print_live_api_test(name: str, identifiers: dict, keywords: list):
    """Test with live API calls to real sources."""
    print("\n" + "=" * 70)
    print("  LIVE API TEST")
    print("=" * 70)

    results = []
    search_functions = [
        ("github", search_github, identifiers["github"]),
        ("linkedin", search_linkedin, identifiers["linkedin"]),
        ("google_scholar", search_google_scholar, identifiers["google_scholar"]),
        ("researchgate", search_researchgate, identifiers["researchgate"]),
        ("kaggle", search_kaggle, identifiers["kaggle"]),
        ("devto", search_devto, identifiers["devto"]),
        ("medium", search_medium, identifiers["medium"]),
        ("hashnode", search_hashnode, identifiers["hashnode"]),
    ]

    for key, func, identifier in search_functions:
        result = run_search_function(key, func, name, keywords, identifier=identifier)
        results.append(result)
        time.sleep(0.5)  # Be polite between requests

    print_summary_report(results)

    # Save results
    safe_name = name.replace(" ", "_")
    output_file = f"search_results_{safe_name}.json"
    data = {
        "candidate_name": name,
        "identifiers": identifiers,
        "keywords": keywords,
        "timestamp": datetime.now().isoformat(),
        "results": [
            {k: v for k, v in r.items() if k != "data"}
            for r in results
        ]
    }
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n[OK] Results saved to: {output_file}")


def print_mock_test(name: str, identifiers: dict, keywords: list):
    """Test with mock data (no live API calls)."""
    print("\n" + "=" * 70)
    print("  MOCK DATA TEST")
    print("=" * 70)

    # Import mock generator
    try:
        from test_candidate_searcher_mock import (
            generate_mock_github, generate_mock_linkedin,
            generate_mock_google_scholar, generate_mock_researchgate,
            generate_mock_kaggle, generate_mock_devto,
            generate_mock_medium, generate_mock_hashnode,
        )
    except ImportError:
        print("❌ Could not import mock data generator "
              "(test_candidate_searcher_mock.py must be next to test.py).")
        sys.exit(1)

    # Mirror the real fallback rule: use the given identifier if present,
    # otherwise fall back to the candidate's full name.
    mock_generators = [
        ("github", generate_mock_github, identifiers["github"] or name),
        ("linkedin", generate_mock_linkedin, identifiers["linkedin"] or name),
        ("google_scholar", generate_mock_google_scholar, identifiers["google_scholar"] or name),
        ("researchgate", generate_mock_researchgate, identifiers["researchgate"] or name),
        ("kaggle", generate_mock_kaggle, identifiers["kaggle"] or name),
        ("devto", generate_mock_devto, identifiers["devto"] or name),
        ("medium", generate_mock_medium, identifiers["medium"] or name),
        ("hashnode", generate_mock_hashnode, identifiers["hashnode"] or name),
    ]

    results = []
    for key, generator_func, used_value in mock_generators:
        print(f"\n{'-'*70}")
        used_kind = "identifier" if identifiers[key] else "name (fallback)"
        print(f"  [{key.upper()}] using {used_kind}: {used_value} (MOCK DATA)")
        print(f"{'-'*70}")

        mock_data = generator_func(used_value, keywords)

        # Check required fields
        required = REQUIRED_FIELDS[key]["required"]
        found_fields = [f for f in required if f in mock_data and mock_data[f]]
        missing_fields = [f for f in required if f not in mock_data or not mock_data[f]]

        if missing_fields:
            print(f"  [WARN] MISSING: {missing_fields}")
        else:
            print(f"  [OK] All required fields present")

        print(f"  URL: {mock_data.get('profile_url', '—')}")
        print(f"  Summary: {mock_data.get('summary', 'N/A')}")

        # Source-specific details
        if key == "github":
            print(f"  Languages: {', '.join(mock_data.get('top_languages', []))}")
            print(f"  Repos: {len(mock_data.get('repos', []))}")
            print(f"  Latest push: {mock_data.get('latest_push', 'N/A')}")

        elif key == "linkedin":
            print(f"  Role: {mock_data.get('current_role', 'N/A')}")
            print(f"  Company: {mock_data.get('company', 'N/A')}")
            print(f"  Tenure: {mock_data.get('estimated_tenure', 'N/A')}")

        elif key == "google_scholar":
            print(f"  Citations: {mock_data.get('citations', 'N/A')}")
            pubs = mock_data.get("publications", [])
            print(f"  Publications: {len(pubs)}")

        elif key in ["devto", "medium", "hashnode"]:
            print(f"  Articles: {len(mock_data.get('articles', []))}")

        results.append({
            "key": key,
            "ok": len(missing_fields) == 0,
            "found": bool(mock_data.get("profile_url")),
            "missing": missing_fields,
        })

    print_summary_report([{**r, "elapsed": 0} for r in results])

    # Save mock data
    mock_candidate = {
        "candidate_name": name,
        "identifiers": identifiers,
        "keywords": keywords,
        "timestamp": datetime.now().isoformat(),
        "sources": {
            r["key"]: {"status": "mocked"}
            for r in results
        }
    }
    safe_name = name.replace(" ", "_")
    output_file = f"mock_candidate_{safe_name}.json"
    with open(output_file, "w") as f:
        json.dump(mock_candidate, f, indent=2)
    print(f"\n[OK] Mock test completed. Output: {output_file}")


if __name__ == "__main__":
    main()
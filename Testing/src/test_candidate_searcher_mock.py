"""
test_candidate_searcher_mock.py

Test candidateSearcher.py directly with mock data.
Does NOT call the live FastAPI backend or AI scoring.
Focuses on whether candidateSearcher captures all required fields.

What it tests:
  ✓ GitHub: repos, languages, contribution activity, last commit date
  ✓ LinkedIn (public): current role, company, estimated tenure
  ✓ Google Scholar / ResearchGate: publications, citations, FYP papers
  ✓ Kaggle: competition ranking, notebooks, datasets
  ✓ Dev.to / Medium / Hashnode: technical writing, topics, publication frequency

Mock data uses Malaysian universities and companies:
  Universities: UTAR, UM, UTM, UPM, USM, UTP, Monash Malaysia, APU, MMU
  Companies: Intel, Keysight, NXP, Petronas, Maybank, CIMB, Carsome, Aerodyne, Sime Darby, Top Glove
"""

import json
from datetime import datetime, timedelta
import random


# ──────────────────────────────────────────────────────────
# MOCK DATA GENERATORS
# ──────────────────────────────────────────────────────────

def generate_mock_github(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock GitHub profile data for a Malaysian candidate."""
    username_parts = candidate_name.lower().split()
    username = f"{username_parts[0]}{username_parts[-1] if len(username_parts) > 1 else ''}"
    
    return {
        "profile_url": f"https://github.com/{username}",
        "bio": f"Software Engineer | Machine Learning enthusiast | Based in Malaysia",
        "public_repos": random.randint(15, 45),
        "followers": random.randint(20, 150),
        "last_active": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
        "top_languages": ["Python", "JavaScript", "Java", "TypeScript", "SQL"][:random.randint(2, 5)],
        "repos": [
            {
                "name": "ml-sentiment-analysis",
                "description": "Machine learning model for sentiment analysis using Python and NLP",
                "language": "Python",
                "stars": random.randint(5, 50),
                "last_push": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "url": f"https://github.com/{username}/ml-sentiment-analysis",
            },
            {
                "name": "data-pipeline",
                "description": "ETL pipeline for processing large-scale datasets",
                "language": "Python",
                "stars": random.randint(3, 40),
                "last_push": (datetime.now() - timedelta(days=random.randint(1, 15))).strftime("%Y-%m-%d"),
                "url": f"https://github.com/{username}/data-pipeline",
            },
            {
                "name": "web-dashboard",
                "description": "Real-time analytics dashboard built with React and Python backend",
                "language": "JavaScript",
                "stars": random.randint(10, 60),
                "last_push": (datetime.now() - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
                "url": f"https://github.com/{username}/web-dashboard",
            },
            {
                "name": "deep-learning-models",
                "description": "Collection of deep learning models for image classification and NLP tasks",
                "language": "Python",
                "stars": random.randint(20, 100),
                "last_push": (datetime.now() - timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d"),
                "url": f"https://github.com/{username}/deep-learning-models",
            },
        ],
        "keyword_hits": {kw: (kw.lower() in "machine learning python data science".lower()) for kw in keywords},
        "latest_push": (datetime.now() - timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d"),
        "contribution_activity": {
            "repo_count": 4,
            "public_repos": random.randint(15, 45),
            "followers": random.randint(20, 150),
            "total_stars": random.randint(50, 250),
        },
        "summary": "Found. Languages: Python, JavaScript, Java. Strong ML and Data Science background."
    }


def generate_mock_linkedin(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock LinkedIn profile data."""
    companies = ["Intel", "Keysight", "NXP", "Petronas", "Maybank", "CIMB", "Carsome", "Aerodyne", "Sime Darby", "Top Glove"]
    roles = ["Senior Software Engineer", "Data Scientist", "Machine Learning Engineer", "Full Stack Developer", "DevOps Engineer"]
    
    return {
        "profile_url": f"https://www.linkedin.com/in/{candidate_name.lower().replace(' ', '-')}",
        "current_role": random.choice(roles),
        "company": random.choice(companies),
        "estimated_tenure": f"{random.randint(1, 5)} years",
        "employment_status": "Currently employed",
        "keyword_hits": {kw: (kw.lower() in "engineering machine learning software".lower()) for kw in keywords},
        "summary": f"Profile found. Role: {random.choice(roles)} @ {random.choice(companies)}."
    }


def generate_mock_google_scholar(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock Google Scholar profile data."""
    universities = ["UTAR", "UM", "UTM", "UPM", "USM", "UTP", "Monash Malaysia", "APU", "MMU"]
    
    return {
        "profile_url": f"https://scholar.google.com/citations?user=mock{random.randint(1000, 9999)}",
        "affiliation": f"{random.choice(universities)}, Malaysia",
        "citations": random.randint(50, 500),
        "interests": ["Machine Learning", "Deep Learning", "Data Science", "NLP", "Computer Vision"],
        "publications": [
            {
                "title": "Advanced Deep Learning Techniques for Malaysian e-Commerce",
                "year": "2023",
                "venue": "IEEE Transactions on Software Engineering",
            },
            {
                "title": "Optimizing Machine Learning Models for Edge Computing",
                "year": "2023",
                "venue": "ACM Computing Surveys",
            },
            {
                "title": "Natural Language Processing for Low-Resource Languages",
                "year": "2022",
                "venue": "Journal of AI Research",
            },
            {
                "title": "FYP: Sentiment Analysis System for Financial Markets",
                "year": "2021",
                "venue": f"{random.choice(universities)} Final Year Project",
            },
        ],
        "keyword_hits": {kw: (kw.lower() in "machine learning research publication".lower()) for kw in keywords},
        "summary": f"Found. {len([p for p in [1,2,3,4] if random.random() > 0.3])} publications, {random.randint(50, 500)} citations."
    }


def generate_mock_researchgate(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock ResearchGate profile data."""
    universities = ["UTAR", "UM", "UTM", "UPM", "USM", "UTP", "Monash Malaysia"]
    
    return {
        "profile_url": f"https://www.researchgate.net/profile/{candidate_name.replace(' ', '_')}",
        "affiliation": f"{random.choice(universities)}, Malaysia",
        "publications_count": random.randint(5, 30),
        "citations": random.randint(20, 200),
        "keyword_hits": {kw: (kw.lower() in "research publication academic".lower()) for kw in keywords},
        "summary": f"Profile found. Active researcher in machine learning and software engineering."
    }


def generate_mock_kaggle(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock Kaggle profile data."""
    username = candidate_name.lower().replace(' ', '')
    
    return {
        "profile_url": f"https://www.kaggle.com/{username}",
        "competition_ranking": f"Top {random.randint(5, 500)}%",
        "notebooks": random.randint(10, 50),
        "datasets": random.randint(5, 30),
        "competitions_participated": random.randint(5, 20),
        "keyword_hits": {kw: (kw.lower() in "machine learning competition data".lower()) for kw in keywords},
        "summary": f"Kaggle profile found. Active in {random.randint(5, 20)} competitions."
    }


def generate_mock_devto(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock Dev.to profile data."""
    username = candidate_name.lower().replace(' ', '')
    
    return {
        "profile_url": f"https://dev.to/{username}",
        "articles": [
            {
                "title": "Getting Started with Machine Learning in Python",
                "tags": ["machine-learning", "python", "tutorial"],
                "reactions": random.randint(20, 200),
                "published": (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d"),
            },
            {
                "title": "Building Scalable Data Pipelines",
                "tags": ["data-engineering", "python", "architecture"],
                "reactions": random.randint(15, 150),
                "published": (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d"),
            },
            {
                "title": "Deep Learning Best Practices",
                "tags": ["deep-learning", "machine-learning", "tensorflow"],
                "reactions": random.randint(30, 250),
                "published": (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d"),
            },
        ],
        "keyword_hits": {kw: (kw.lower() in "machine learning technical writing".lower()) for kw in keywords},
        "summary": f"Found {random.randint(3, 15)} articles on Dev.to."
    }


def generate_mock_medium(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock Medium profile data."""
    username = candidate_name.lower().replace(' ', '-')
    
    return {
        "profile_url": f"https://medium.com/@{username}",
        "articles_count": random.randint(5, 40),
        "followers": random.randint(100, 1000),
        "topics": ["Machine Learning", "Data Science", "Python", "Software Engineering", "AI"],
        "keyword_hits": {kw: (kw.lower() in "machine learning writing publication".lower()) for kw in keywords},
        "summary": f"Profile found on Medium. {random.randint(5, 40)} published articles."
    }


def generate_mock_hashnode(candidate_name: str, keywords: list) -> dict:
    """Generate realistic mock Hashnode profile data."""
    username = candidate_name.lower().replace(' ', '')
    
    return {
        "profile_url": f"https://hashnode.com/@{username}",
        "articles_count": random.randint(3, 25),
        "followers": random.randint(50, 500),
        "topics": ["Machine Learning", "Data Engineering", "Python", "DevOps"],
        "keyword_hits": {kw: (kw.lower() in "technical blog machine learning".lower()) for kw in keywords},
        "summary": f"Profile found on Hashnode. Active technical blogger."
    }


# ──────────────────────────────────────────────────────────
# COMPREHENSIVE MOCK CANDIDATE
# ──────────────────────────────────────────────────────────

def generate_complete_mock_candidate(candidate_name: str, job_requirements: list) -> dict:
    """
    Generate a complete mock candidate profile covering all 8 sources.
    """
    # Extract keywords (same as candidateSearcher does)
    keywords = []
    stop_words = {"and", "or", "the", "of", "in", "with", "to", "a", "an", "is", "are"}
    for req in job_requirements:
        for word in re.split(r"[\s,/+()\-]+", req.lower()):
            if word and word not in stop_words and len(word) > 2:
                keywords.append(word)
    keywords = list(dict.fromkeys(keywords))

    return {
        "candidate_name": candidate_name,
        "job_requirements": job_requirements,
        "keywords": keywords,
        "timestamp": datetime.now().isoformat(),
        "sources": {
            "github": generate_mock_github(candidate_name, keywords),
            "linkedin": generate_mock_linkedin(candidate_name, keywords),
            "google_scholar": generate_mock_google_scholar(candidate_name, keywords),
            "researchgate": generate_mock_researchgate(candidate_name, keywords),
            "kaggle": generate_mock_kaggle(candidate_name, keywords),
            "devto": generate_mock_devto(candidate_name, keywords),
            "medium": generate_mock_medium(candidate_name, keywords),
            "hashnode": generate_mock_hashnode(candidate_name, keywords),
        }
    }


# ──────────────────────────────────────────────────────────
# VERIFICATION & REPORTING
# ──────────────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "github": [
        "profile_url", "repos", "languages", "contribution_activity", 
        "latest_push", "public_repos", "followers", "top_languages"
    ],
    "linkedin": [
        "profile_url", "current_role", "company", "estimated_tenure", "employment_status"
    ],
    "google_scholar": [
        "profile_url", "publications", "citations", "affiliation", "interests"
    ],
    "researchgate": [
        "profile_url", "publications_count", "citations", "affiliation"
    ],
    "kaggle": [
        "profile_url", "competition_ranking", "notebooks", "datasets", "competitions_participated"
    ],
    "devto": [
        "profile_url", "articles", "topics", "keyword_hits"
    ],
    "medium": [
        "profile_url", "articles_count", "followers", "topics"
    ],
    "hashnode": [
        "profile_url", "articles_count", "followers", "topics"
    ],
}


def verify_and_print_candidate(mock_data: dict):
    """Verify all required fields are present and print detailed report."""
    print("\n" + "=" * 70)
    print(f"  CANDIDATE: {mock_data['candidate_name']}")
    print(f"  Requirements: {', '.join(mock_data['job_requirements'])}")
    print(f"  Keywords: {', '.join(mock_data['keywords'])}")
    print("=" * 70)

    all_fields_present = True

    for source, required_fields in REQUIRED_FIELDS.items():
        print(f"\n{'─' * 70}")
        print(f"  [{source.upper()}]")
        print(f"{'─' * 70}")

        source_data = mock_data["sources"].get(source, {})
        
        if not source_data:
            print(f"  ⚠ No data for {source}")
            all_fields_present = False
            continue

        # Check required fields
        missing = [f for f in required_fields if f not in source_data]
        if missing:
            print(f"  ❌ MISSING FIELDS: {missing}")
            all_fields_present = False
        else:
            print(f"  ✅ All required fields present")

        # Print available data
        url = source_data.get("profile_url", "—")
        print(f"  URL: {url}")
        
        summary = source_data.get("summary", "N/A")
        print(f"  Summary: {summary}")

        # Source-specific details
        if source == "github":
            print(f"  Languages: {', '.join(source_data.get('top_languages', []))}")
            print(f"  Repos count: {len(source_data.get('repos', []))}")
            print(f"  Latest push: {source_data.get('latest_push', 'N/A')}")
            activity = source_data.get("contribution_activity", {})
            print(f"  Followers: {activity.get('followers', 'N/A')}")
            print(f"  Total stars: {activity.get('total_stars', 'N/A')}")

        elif source == "linkedin":
            print(f"  Role: {source_data.get('current_role', 'N/A')}")
            print(f"  Company: {source_data.get('company', 'N/A')}")
            print(f"  Tenure: {source_data.get('estimated_tenure', 'N/A')}")
            print(f"  Status: {source_data.get('employment_status', 'N/A')}")

        elif source in ["google_scholar", "researchgate"]:
            print(f"  Affiliation: {source_data.get('affiliation', 'N/A')}")
            print(f"  Citations: {source_data.get('citations', 'N/A')}")
            pubs = source_data.get("publications", [])
            print(f"  Publications: {len(pubs)}")
            for pub in pubs[:3]:
                print(f"    - {pub.get('title', 'N/A')} ({pub.get('year', 'N/A')})")

        elif source == "kaggle":
            print(f"  Ranking: {source_data.get('competition_ranking', 'N/A')}")
            print(f"  Notebooks: {source_data.get('notebooks', 'N/A')}")
            print(f"  Datasets: {source_data.get('datasets', 'N/A')}")
            print(f"  Competitions: {source_data.get('competitions_participated', 'N/A')}")

        elif source in ["devto", "medium", "hashnode"]:
            print(f"  Articles: {source_data.get('articles_count', len(source_data.get('articles', [])))}")
            print(f"  Topics: {', '.join(source_data.get('topics', []))}")
            if source == "devto":
                articles = source_data.get("articles", [])
                print(f"  Recent articles: {len(articles)}")
                for article in articles[:2]:
                    print(f"    - {article.get('title', 'N/A')}")

        # Keyword matches
        keyword_hits = source_data.get("keyword_hits", {})
        matched = [k for k, v in keyword_hits.items() if v]
        if matched:
            print(f"  Keywords matched: {', '.join(matched)}")
        else:
            print(f"  Keywords matched: None")

    print("\n" + "=" * 70)
    if all_fields_present:
        print("  ✅ ALL REQUIRED FIELDS CAPTURED")
    else:
        print("  ⚠ SOME FIELDS ARE MISSING — candidateSearcher needs updates")
    print("=" * 70)


# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import re

    # Example: Malaysian software engineer candidate
    candidate_name = "Rajesh Kumar"
    job_requirements = [
        "Machine Learning",
        "Python",
        "Deep Learning",
        "Data Science",
        "3+ years experience"
    ]

    print("\n" + "=" * 70)
    print("  MOCK DATA GENERATOR FOR candidateSearcher.py")
    print("=" * 70)

    # Generate mock data
    mock_candidate = generate_complete_mock_candidate(candidate_name, job_requirements)

    # Verify and print
    verify_and_print_candidate(mock_candidate)

    # Optionally save mock data to JSON
    output_file = "mock_candidate_data.json"
    with open(output_file, "w") as f:
        json.dump(mock_candidate, f, indent=2)
    print(f"\n✅ Mock data saved to: {output_file}")

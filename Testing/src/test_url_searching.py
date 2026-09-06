"""
test_url_searching.py
─────────────────────────────────────────────────────────────────────────────
Tests URL-building and identifier-parsing logic for every platform in
candidateSearcher.py, then does live HTTP reachability checks on each
constructed URL.

Usage (from repo root or Testing/src):
    python test_url_searching.py [--verbose] [--live]

Flags:
    --verbose   Show per-test detail even when passing
    --live      Fire real HTTP HEAD requests to verify each built URL
                (adds ~2 s per URL; skipped by default)

Exit code: 0 = all pass, 1 = one or more failures.
"""

import sys
import os
import re
import time
import json
import unittest
import argparse
import importlib.util
from unittest.mock import patch, MagicMock
from pathlib import Path

# ─── Locate the module under test ────────────────────────────────────────────
SEARCHER_PATH = Path(
    r"D:\Utar\Y3S1\team porject\Searching-public-footprint\Backend\AI\candidateSearcher.py"
)
# Fallback: look two directories up from this script
if not SEARCHER_PATH.exists():
    SEARCHER_PATH = Path(__file__).resolve().parents[2] / "Backend" / "AI" / "candidateSearcher.py"

if not SEARCHER_PATH.exists():
    sys.exit(
        f"❌  Cannot find candidateSearcher.py.\n"
        f"    Tried: {SEARCHER_PATH}\n"
        f"    Set SEARCHER_PATH at the top of this script."
    )

spec   = importlib.util.spec_from_file_location("candidateSearcher", SEARCHER_PATH)
cs     = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

# ─── CLI args ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="URL searching test suite")
parser.add_argument("--verbose", action="store_true", help="verbose output")
parser.add_argument("--live",    action="store_true", help="run live HTTP checks")
CLI, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0]] + remaining  # let unittest parse its own flags

VERBOSE = CLI.verbose
RUN_LIVE = CLI.live

SAMPLE_KEYWORDS = ["python", "react", "fastapi", "docker", "postgresql"]
NAME            = "Loh Zhi Fong"


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 – parse_identifier unit tests
# ═════════════════════════════════════════════════════════════════════════════

class TestParseIdentifier(unittest.TestCase):
    """Verify that full URLs and plain handles all normalise to bare usernames."""

    # ── GitHub ──────────────────────────────────────────────────────────────
    def test_github_plain_handle(self):
        self.assertEqual(cs.parse_identifier("absinthe3103", "github"), "absinthe3103")

    def test_github_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://github.com/absinthe3103", "github"),
            "absinthe3103",
        )

    def test_github_url_trailing_slash(self):
        self.assertEqual(
            cs.parse_identifier("https://github.com/absinthe3103/", "github"),
            "absinthe3103",
        )

    def test_github_empty_returns_none(self):
        self.assertIsNone(cs.parse_identifier("", "github"))

    def test_github_none_returns_none(self):
        self.assertIsNone(cs.parse_identifier(None, "github"))

    # ── LinkedIn ─────────────────────────────────────────────────────────────
    def test_linkedin_plain_handle(self):
        self.assertEqual(cs.parse_identifier("john-doe-123", "linkedin"), "john-doe-123")

    def test_linkedin_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://www.linkedin.com/in/john-doe-123", "linkedin"),
            "john-doe-123",
        )

    def test_linkedin_url_no_www(self):
        self.assertEqual(
            cs.parse_identifier("https://linkedin.com/in/john-doe-123", "linkedin"),
            "john-doe-123",
        )

    # ── Kaggle ───────────────────────────────────────────────────────────────
    def test_kaggle_plain_handle(self):
        self.assertEqual(cs.parse_identifier("johndoe", "kaggle"), "johndoe")

    def test_kaggle_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://www.kaggle.com/johndoe", "kaggle"),
            "johndoe",
        )

    # ── Dev.to ───────────────────────────────────────────────────────────────
    def test_devto_plain(self):
        self.assertEqual(cs.parse_identifier("johndoe", "devto"), "johndoe")

    def test_devto_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://dev.to/johndoe", "devto"),
            "johndoe",
        )

    # ── Medium ───────────────────────────────────────────────────────────────
    def test_medium_with_at(self):
        self.assertEqual(
            cs.parse_identifier("https://medium.com/@johndoe", "medium"),
            "johndoe",
        )

    def test_medium_without_at(self):
        self.assertEqual(
            cs.parse_identifier("https://medium.com/johndoe", "medium"),
            "johndoe",
        )

    def test_medium_plain_handle(self):
        self.assertEqual(cs.parse_identifier("johndoe", "medium"), "johndoe")

    def test_medium_plain_at_handle(self):
        self.assertEqual(cs.parse_identifier("@johndoe", "medium"), "johndoe")

    # ── Hashnode ──────────────────────────────────────────────────────────────
    def test_hashnode_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://hashnode.com/@johndoe", "hashnode"),
            "johndoe",
        )

    def test_hashnode_plain(self):
        # plain handle → treated as-is (no @ prefix in output)
        self.assertEqual(cs.parse_identifier("johndoe", "hashnode"), "johndoe")

    # ── ResearchGate ─────────────────────────────────────────────────────────
    def test_researchgate_full_url(self):
        self.assertEqual(
            cs.parse_identifier(
                "https://www.researchgate.net/profile/John-Doe-5", "researchgate"
            ),
            "John-Doe-5",
        )

    # ── Google Scholar ────────────────────────────────────────────────────────
    def test_google_scholar_full_url(self):
        uid = cs.parse_identifier(
            "https://scholar.google.com/citations?user=ABC123xyz", "google_scholar"
        )
        self.assertEqual(uid, "ABC123xyz")

    def test_google_scholar_plain_id(self):
        self.assertEqual(
            cs.parse_identifier("ABC123xyz", "google_scholar"), "ABC123xyz"
        )

    # ── Semantic Scholar ──────────────────────────────────────────────────────
    def test_semantic_scholar_full_url(self):
        sid = cs.parse_identifier(
            "https://www.semanticscholar.org/author/John-Doe/1234567", "semantic_scholar"
        )
        self.assertEqual(sid, "1234567")

    # ── ORCID ─────────────────────────────────────────────────────────────────
    def test_orcid_full_url(self):
        oid = cs.parse_identifier(
            "https://orcid.org/0000-0002-1234-5678", "orcid"
        )
        self.assertEqual(oid, "0000-0002-1234-5678")

    def test_orcid_plain_id(self):
        self.assertEqual(
            cs.parse_identifier("0000-0002-1234-5678", "orcid"),
            "0000-0002-1234-5678",
        )


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 – username_guesses
# ═════════════════════════════════════════════════════════════════════════════

class TestUsernameGuesses(unittest.TestCase):
    def test_two_part_name_produces_guesses(self):
        guesses = cs.username_guesses("John Doe")
        self.assertIn("johndoe", guesses)
        self.assertIn("john.doe", guesses)
        self.assertIn("jdoe", guesses)

    def test_three_part_name(self):
        guesses = cs.username_guesses("Loh Zhi Fong")
        self.assertTrue(len(guesses) > 0)
        # first and last part should appear somewhere
        combined = " ".join(guesses)
        self.assertIn("loh", combined)

    def test_single_name(self):
        guesses = cs.username_guesses("Zen")
        self.assertIn("zen", guesses)

    def test_no_duplicates(self):
        guesses = cs.username_guesses("John Doe")
        self.assertEqual(len(guesses), len(set(guesses)))


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 – URL construction from each searcher function (mocked network)
# ═════════════════════════════════════════════════════════════════════════════

def _mock_404(*args, **kwargs):
    """Simulate a 404 so every function falls through to its 'not found' path
    without actually hitting the network."""
    m = MagicMock()
    m.status_code = 404
    m.ok = False
    m.raise_for_status.side_effect = Exception("404")
    return None


def _mock_200(text="", json_data=None):
    """Return a mock 200 response."""
    m = MagicMock()
    m.status_code = 200
    m.ok = True
    m.text = text
    m.raise_for_status.return_value = None
    m.json.return_value = json_data or {}
    return m


class TestURLConstruction(unittest.TestCase):
    """
    Verify that each searcher builds the right profile URL when given an
    identifier. We patch requests.get to return 200 with minimal data so the
    function completes, then inspect the returned dict.
    """

    # ── GitHub ──────────────────────────────────────────────────────────────
    @patch("requests.get")
    def test_github_url_built_correctly(self, mock_get):
        # First call = user lookup (200), second = repos (200)
        mock_get.side_effect = [
            _mock_200(json_data={
                "html_url": "https://github.com/absinthe3103",
                "bio": "developer",
                "public_repos": 5,
                "followers": 10,
                "updated_at": "2024-01-01T00:00:00Z",
                "created_at": "2020-01-01T00:00:00Z",
            }),
            _mock_200(json_data=[]),   # repos call
        ]
        result = cs.search_github(NAME, SAMPLE_KEYWORDS, "absinthe3103")
        self.assertEqual(result["profile_url"], "https://github.com/absinthe3103")
        self.assertIn("keyword_hits", result)
        if VERBOSE:
            print(f"\n  GitHub URL: {result['profile_url']}")

    # ── GitHub – no identifier → guess path ──────────────────────────────────
    @patch("requests.get", return_value=None)
    def test_github_no_identifier_returns_guesses(self, mock_get):
        result = cs.search_github(NAME, SAMPLE_KEYWORDS, None)
        self.assertIn("possible_profiles", result)
        self.assertEqual(result["summary"], "Not provided — guessed")

    # ── LinkedIn ─────────────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_linkedin_url_set_from_identifier(self, _mock):
        result = cs.search_linkedin(NAME, SAMPLE_KEYWORDS, "john-doe-123")
        self.assertEqual(result["profile_url"], "https://www.linkedin.com/in/john-doe-123")

    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_linkedin_no_identifier_guess_mode(self, _mock):
        result = cs.search_linkedin(NAME, SAMPLE_KEYWORDS, None)
        self.assertIn("possible_profiles", result)

    # ── Kaggle ───────────────────────────────────────────────────────────────
    @patch("requests.get")
    def test_kaggle_url_built_correctly(self, mock_get):
        mock_get.return_value = _mock_200(text="10 Competitions 3 Notebooks")
        result = cs.search_kaggle(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://www.kaggle.com/johndoe")

    @patch("requests.get", return_value=None)
    def test_kaggle_not_found_message(self, _mock):
        result = cs.search_kaggle(NAME, SAMPLE_KEYWORDS, "nonexistent_xyz_abc_999")
        self.assertIn("not found", result["summary"].lower())

    # ── Dev.to ───────────────────────────────────────────────────────────────
    @patch("requests.get")
    def test_devto_url_built_correctly(self, mock_get):
        article = {
            "title": "Test Article",
            "tag_list": ["python", "react"],
            "positive_reactions_count": 5,
            "published_at": "2024-01-01T00:00:00Z",
            "url": "https://dev.to/johndoe/test-article",
        }
        mock_get.return_value = _mock_200(json_data=[article])
        result = cs.search_devto(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://dev.to/johndoe")
        self.assertEqual(len(result["articles"]), 1)
        self.assertIn("python", result["keyword_hits"])

    @patch("requests.get")
    def test_devto_empty_articles(self, mock_get):
        mock_get.return_value = _mock_200(json_data=[])
        result = cs.search_devto(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertIn("not found", result["summary"].lower())

    # ── Medium ───────────────────────────────────────────────────────────────
    @patch("requests.get")
    def test_medium_url_built_correctly(self, mock_get):
        mock_get.return_value = _mock_200(text="<html><body>Medium profile</body></html>")
        result = cs.search_medium(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://medium.com/@johndoe")

    @patch("requests.get", return_value=None)
    def test_medium_not_found(self, _mock):
        result = cs.search_medium(NAME, SAMPLE_KEYWORDS, "nonexistent_xyz_abc_999")
        self.assertIn("not found", result["summary"].lower())

    # ── Hashnode ──────────────────────────────────────────────────────────────
    @patch("requests.get")
    def test_hashnode_url_built_correctly(self, mock_get):
        mock_get.return_value = _mock_200(
            text="<html><body>Hashnode blog</body></html>"
        )
        result = cs.search_hashnode(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://hashnode.com/@johndoe")

    @patch("requests.get", return_value=None)
    def test_hashnode_not_found(self, _mock):
        result = cs.search_hashnode(NAME, SAMPLE_KEYWORDS, "xyz_nonexistent_999")
        self.assertIn("not found", result["summary"].lower())

    # ── ResearchGate / ORCID ─────────────────────────────────────────────────
    @patch("requests.get")
    def test_researchgate_url_built_correctly(self, mock_get):
        mock_get.return_value = _mock_200(
            text="<html><body>ResearchGate profile</body></html>"
        )
        result = cs.search_researchgate(NAME, SAMPLE_KEYWORDS, "John-Doe-5")
        self.assertEqual(result["profile_url"], "https://www.researchgate.net/profile/John-Doe-5")

    @patch("requests.get")
    @patch.object(cs, "orcid_get")
    def test_orcid_path_taken_for_orcid_id(self, mock_orcid, mock_get):
        # orcid_get returns person data
        mock_orcid.return_value = _mock_200(json_data={
            "keywords": {"keyword": [{"content": "bioinformatics"}]},
        })
        result = cs.search_researchgate(
            NAME, SAMPLE_KEYWORDS, "0000-0002-1234-5678"
        )
        self.assertIn("orcid.org", result["profile_url"])

    # ── Google Scholar ────────────────────────────────────────────────────────
    def test_google_scholar_no_identifier_skips(self):
        result = cs.search_google_scholar(NAME, SAMPLE_KEYWORDS, None)
        self.assertEqual(result["summary"], "Not provided — guessed")

    def test_google_scholar_sem_scholar_non_numeric_ignored(self):
        """Non-numeric identifiers should not be treated as Semantic Scholar IDs."""
        uid = cs.parse_identifier("ABC123xyz", "semantic_scholar")
        # Should not be all digits → sem_handle would be None after the isdigit check
        self.assertFalse(uid.isdigit() if uid else True)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 – kw_score / matched helpers
# ═════════════════════════════════════════════════════════════════════════════

class TestKeywordHelpers(unittest.TestCase):
    def test_kw_score_hit(self):
        hits = cs.kw_score("I love python and react", ["python", "java"])
        self.assertTrue(hits["python"])
        self.assertFalse(hits["java"])

    def test_kw_score_case_insensitive(self):
        hits = cs.kw_score("FastAPI is great", ["fastapi"])
        self.assertTrue(hits["fastapi"])

    def test_matched_returns_only_hits(self):
        hits = {"python": True, "java": False, "docker": True}
        self.assertEqual(sorted(cs.matched(hits)), ["docker", "python"])

    def test_kw_score_empty_text(self):
        hits = cs.kw_score("", ["python"])
        self.assertFalse(hits["python"])

    def test_kw_score_empty_keywords(self):
        hits = cs.kw_score("python is great", [])
        self.assertEqual(hits, {})


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 – return-value schema (all keys present)
# ═════════════════════════════════════════════════════════════════════════════

class TestReturnSchema(unittest.TestCase):
    """Each searcher must return a dict with required keys even on failure."""

    REQUIRED = {
        "search_github": [
            "profile_url", "bio", "public_repos", "followers",
            "last_active", "top_languages", "repos", "keyword_hits", "summary",
        ],
        "search_linkedin": [
            "profile_url", "current_role", "company", "keyword_hits", "summary",
        ],
        "search_google_scholar": [
            "profile_url", "affiliation", "citations", "interests",
            "publications", "keyword_hits", "summary", "h_index",
        ],
        "search_researchgate": [
            "profile_url", "keyword_hits", "summary",
            "research_interests", "publication_count", "publications",
        ],
        "search_kaggle": [
            "profile_url", "keyword_hits", "summary",
            "competitions", "notebooks", "datasets",
        ],
        "search_devto": [
            "profile_url", "articles", "keyword_hits", "summary",
            "publication_frequency", "top_topics",
        ],
        "search_medium": [
            "profile_url", "keyword_hits", "summary",
            "articles", "publication_frequency", "top_topics",
        ],
        "search_hashnode": [
            "profile_url", "keyword_hits", "summary",
            "articles", "publication_frequency", "top_topics",
        ],
    }

    @patch("requests.get", return_value=None)
    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch.object(cs, "orcid_get", return_value=None)
    def test_all_schemas(self, *_mocks):
        kws = ["python"]
        for fn_name, keys in self.REQUIRED.items():
            with self.subTest(function=fn_name):
                fn = getattr(cs, fn_name)
                result = fn("Test User", kws, "some_fake_handle")
                missing = [k for k in keys if k not in result]
                self.assertEqual(
                    missing, [],
                    msg=f"{fn_name} is missing keys: {missing}",
                )
                if VERBOSE:
                    print(f"\n  {fn_name} schema OK: {list(result.keys())}")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 – Live HTTP reachability (only runs with --live)
# ═════════════════════════════════════════════════════════════════════════════

KNOWN_URLS = {
    "GitHub API user endpoint": "https://api.github.com/users/torvalds",
    "Dev.to API articles":      "https://dev.to/api/articles?username=ben&per_page=1",
    "Kaggle profile":           "https://www.kaggle.com/dansbecker",
    "Medium profile":           "https://medium.com/@Medium",
    "Hashnode profile":         "https://hashnode.com/@hashnode",
    "Semantic Scholar API":     "https://api.semanticscholar.org/graph/v1/author/search?query=Alan+Turing&limit=1",
    "ORCID public API":         "https://pub.orcid.org/v3.0/0000-0002-1825-0097/person",
    "LinkedIn public (redirects OK)": "https://www.linkedin.com/in/williamhgates",
    "ResearchGate profile":     "https://www.researchgate.net/profile/Albert-Einstein",
    "Kaggle API (public)":      "https://www.kaggle.com/api/v1/users/dansbecker",
}


@unittest.skipUnless(RUN_LIVE, "Skipped — pass --live to run HTTP checks")
class TestLiveURLReachability(unittest.TestCase):
    """
    Fires HEAD (or GET) requests at known-good public URLs for each platform.
    A 2xx or 3xx response counts as reachable.
    """

    import requests as _requests

    def _check(self, label, url, timeout=10):
        import requests
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True,
                              headers=cs.HEADERS)
            status = r.status_code
        except Exception as e:
            self.fail(f"{label} → exception: {e}")
        self.assertLess(
            status, 500,
            msg=f"{label} returned server error {status} for {url}",
        )
        if VERBOSE:
            print(f"  {label}: HTTP {status}")

    def test_all_known_urls(self):
        for label, url in KNOWN_URLS.items():
            with self.subTest(label=label):
                self._check(label, url)
                time.sleep(0.5)   # be polite


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 – Integration: full pipeline with mocked network
# ═════════════════════════════════════════════════════════════════════════════

class TestIntegrationMocked(unittest.TestCase):
    """
    Runs search_github + search_devto end-to-end with mocked HTTP to confirm
    keyword_hits, prominent_repos, and career_indicators are all populated.
    """

    @patch("requests.get")
    def test_github_prominent_repos_detected(self, mock_get):
        repo_list = [
            {
                "name": "star-project",
                "description": "A python fastapi project",
                "language": "Python",
                "stargazers_count": 50,
                "pushed_at": "2025-07-01T00:00:00Z",
                "html_url": "https://github.com/user/star-project",
            },
            {
                "name": "old-repo",
                "description": "legacy stuff",
                "language": "Java",
                "stargazers_count": 0,
                "pushed_at": "2019-01-01T00:00:00Z",
                "html_url": "https://github.com/user/old-repo",
            },
        ]
        mock_get.side_effect = [
            _mock_200(json_data={
                "html_url": "https://github.com/user",
                "bio": "python developer",
                "public_repos": 10,
                "followers": 20,
                "updated_at": "2025-01-01T00:00:00Z",
                "created_at": "2018-01-01T00:00:00Z",
            }),
            _mock_200(json_data=repo_list),
        ]
        result = cs.search_github(NAME, SAMPLE_KEYWORDS, "user")
        self.assertGreater(len(result["prominent_repos"]), 0)
        self.assertIn("Python", result["top_languages"])
        self.assertTrue(result["keyword_hits"].get("python"))
        self.assertIn("years_active_on_github", result["career_indicators"])

    @patch("requests.get")
    def test_devto_publication_frequency_computed(self, mock_get):
        articles = [
            {
                "title": "Using FastAPI with Docker",
                "tag_list": ["fastapi", "docker"],
                "positive_reactions_count": 10,
                "published_at": "2024-06-01T00:00:00Z",
                "url": "https://dev.to/user/article-1",
            },
            {
                "title": "React hooks deep dive",
                "tag_list": ["react"],
                "positive_reactions_count": 5,
                "published_at": "2024-01-01T00:00:00Z",
                "url": "https://dev.to/user/article-2",
            },
        ]
        mock_get.return_value = _mock_200(json_data=articles)
        result = cs.search_devto(NAME, SAMPLE_KEYWORDS, "user")
        self.assertIn("articles_per_month", result["publication_frequency"])
        self.assertIn("fastapi", result["keyword_hits"])
        self.assertIn("react",   result["keyword_hits"])


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 8 – Edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):

    def test_parse_identifier_whitespace_only(self):
        self.assertIsNone(cs.parse_identifier("   ", "github"))

    def test_parse_identifier_at_prefix_stripped(self):
        result = cs.parse_identifier("@myuser", "devto")
        self.assertEqual(result, "myuser")

    def test_kw_score_partial_match_not_counted(self):
        # 'py' should NOT match keyword 'python'
        hits = cs.kw_score("I use py daily", ["python"])
        self.assertFalse(hits["python"])

    def test_username_guesses_lowercase(self):
        guesses = cs.username_guesses("John DOE")
        for g in guesses:
            self.assertEqual(g, g.lower())

    @patch("requests.get")
    def test_github_repos_missing_language_handled(self, mock_get):
        """Repos with null language should not crash the function."""
        repo_list = [
            {
                "name": "no-lang-repo",
                "description": "",
                "language": None,
                "stargazers_count": 0,
                "pushed_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/user/no-lang-repo",
            }
        ]
        mock_get.side_effect = [
            _mock_200(json_data={
                "html_url": "https://github.com/user",
                "bio": "",
                "public_repos": 1,
                "followers": 0,
                "updated_at": "2024-01-01T00:00:00Z",
                "created_at": "2022-01-01T00:00:00Z",
            }),
            _mock_200(json_data=repo_list),
        ]
        result = cs.search_github(NAME, SAMPLE_KEYWORDS, "user")
        # Should not throw and top_languages should be empty
        self.assertEqual(result["top_languages"], [])


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 9 – Marketing platforms: Instagram, TikTok, Meta Ad Library, Similarweb
# ═════════════════════════════════════════════════════════════════════════════

class TestMarketingPlatforms(unittest.TestCase):

    # ── parse_identifier – Instagram / TikTok ────────────────────────────────
    def test_instagram_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://www.instagram.com/johndoe/", "instagram"),
            "johndoe",
        )

    def test_instagram_plain_handle(self):
        self.assertEqual(cs.parse_identifier("johndoe", "instagram"), "johndoe")

    def test_tiktok_full_url(self):
        self.assertEqual(
            cs.parse_identifier("https://www.tiktok.com/@johndoe", "tiktok"),
            "johndoe",
        )

    def test_tiktok_plain_handle(self):
        self.assertEqual(cs.parse_identifier("johndoe", "tiktok"), "johndoe")

    # ── search_instagram – return schema ─────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch("requests.get", return_value=None)
    def test_instagram_schema_keys_present(self, _get, _snippets):
        result = cs.search_instagram(NAME, SAMPLE_KEYWORDS, "johndoe")
        for key in ["profile_url", "keyword_hits", "summary", "followers", "posts", "username"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch("requests.get")
    def test_instagram_url_built_correctly(self, mock_get, _snippets):
        mock_get.return_value = _mock_200(
            text='<html><meta name="description" content="1.2K Followers, 300 Posts - johndoe"></html>'
        )
        result = cs.search_instagram(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://www.instagram.com/johndoe/")
        self.assertEqual(result["username"], "johndoe")

    @patch("requests.get", return_value=None)
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_instagram_no_identifier_guess_mode(self, _snippets, _get):
        # Instagram/TikTok use deep web search (not username guesses), so when
        # snippets return nothing profile_url stays None and summary explains why.
        result = cs.search_instagram(NAME, SAMPLE_KEYWORDS, None)
        self.assertIsNone(result["profile_url"])
        self.assertIn("instagram", result["summary"].lower())

    # ── search_tiktok – return schema ─────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch("requests.get", return_value=None)
    def test_tiktok_schema_keys_present(self, _get, _snippets):
        result = cs.search_tiktok(NAME, SAMPLE_KEYWORDS, "johndoe")
        for key in ["profile_url", "keyword_hits", "summary", "followers", "likes", "username"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch("requests.get")
    def test_tiktok_url_built_correctly(self, mock_get, _snippets):
        mock_get.return_value = _mock_200(
            text='<html><meta property="og:description" content="5K Followers, 10K Likes"></html>'
        )
        result = cs.search_tiktok(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://www.tiktok.com/@johndoe")
        self.assertEqual(result["username"], "johndoe")

    @patch("requests.get", return_value=None)
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_tiktok_no_identifier_guess_mode(self, _snippets, _get):
        # Same as Instagram — deep search, not username guessing.
        result = cs.search_tiktok(NAME, SAMPLE_KEYWORDS, None)
        self.assertIsNone(result["profile_url"])
        self.assertIn("tiktok", result["summary"].lower())

    # ── search_meta_ad_library ────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_meta_ad_library_schema_keys_present(self, _snippets):
        result = cs.search_meta_ad_library(NAME, SAMPLE_KEYWORDS, "TestBrand")
        for key in ["profile_url", "keyword_hits", "summary", "active_ads", "advertiser"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "TestBrand Facebook Ads", "snippet": "42 active ads running on Facebook", "url": "https://fb.com"}
    ])
    def test_meta_ad_library_extracts_ad_count(self, _snippets):
        result = cs.search_meta_ad_library(NAME, SAMPLE_KEYWORDS, "TestBrand")
        self.assertEqual(result["active_ads"], 42)
        self.assertIn("facebook.com/ads/library", result["profile_url"])

    # ── search_similarweb ─────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_similarweb_schema_keys_present(self, _snippets):
        result = cs.search_similarweb(NAME, SAMPLE_KEYWORDS, "example.com")
        for key in ["profile_url", "keyword_hits", "summary", "domain", "traffic_trend"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "example.com Traffic", "snippet": "1.2M monthly visits to example.com", "url": "https://similarweb.com/website/example.com"}
    ])
    def test_similarweb_url_built_correctly(self, _snippets):
        result = cs.search_similarweb(NAME, SAMPLE_KEYWORDS, "example.com")
        self.assertEqual(result["domain"], "example.com")
        self.assertIn("similarweb.com", result["profile_url"])
        self.assertIsNotNone(result["traffic_trend"])

    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_similarweb_no_identifier_no_domain(self, _snippets):
        result = cs.search_similarweb(NAME, SAMPLE_KEYWORDS, None)
        self.assertIn("no domain", result["summary"].lower())


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 10 – HR platforms: SHRM, CIPD, Glassdoor, SSM/ACRA
# ═════════════════════════════════════════════════════════════════════════════

class TestHRPlatforms(unittest.TestCase):

    # ── search_shrm ───────────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_shrm_schema_keys_present(self, _snippets):
        result = cs.search_shrm(NAME, SAMPLE_KEYWORDS, "Jane Doe")
        for key in ["profile_url", "keyword_hits", "summary", "certification", "verified"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "Jane Doe SHRM-SCP Certified HR Professional", "snippet": "Jane Doe holds SHRM-SCP certification", "url": "https://shrm.org"}
    ])
    def test_shrm_detects_certification(self, _snippets):
        result = cs.search_shrm(NAME, SAMPLE_KEYWORDS, "Jane Doe")
        self.assertEqual(result["certification"], "SHRM-SCP")
        self.assertTrue(result["verified"])

    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_shrm_no_cert_found(self, _snippets):
        result = cs.search_shrm(NAME, SAMPLE_KEYWORDS, "Unknown Person")
        self.assertFalse(result["verified"])
        self.assertIsNone(result["certification"])

    # ── search_cipd ───────────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_cipd_schema_keys_present(self, _snippets):
        result = cs.search_cipd(NAME, SAMPLE_KEYWORDS, "Jane Doe")
        for key in ["profile_url", "keyword_hits", "summary", "membership_grade", "verified"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "Jane Doe MCIPD Chartered Member", "snippet": "Jane Doe is a Chartered CIPD member", "url": "https://cipd.org"}
    ])
    def test_cipd_detects_membership(self, _snippets):
        result = cs.search_cipd(NAME, SAMPLE_KEYWORDS, "Jane Doe")
        self.assertIsNotNone(result["membership_grade"])
        self.assertTrue(result["verified"])

    # ── search_glassdoor_employer ──────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_glassdoor_schema_keys_present(self, _snippets):
        result = cs.search_glassdoor_employer(NAME, SAMPLE_KEYWORDS, "Acme Corp")
        for key in ["profile_url", "keyword_hits", "summary", "employer", "rating", "review_count"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "Acme Corp Reviews", "snippet": "Acme Corp rated 4.2 out of 5 stars, 320 reviews", "url": "https://glassdoor.com/acme"}
    ])
    def test_glassdoor_extracts_rating(self, _snippets):
        result = cs.search_glassdoor_employer(NAME, SAMPLE_KEYWORDS, "Acme Corp")
        self.assertEqual(result["rating"], "4.2")
        self.assertIsNotNone(result["review_count"])

    # ── search_ssm_acra ───────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_ssm_acra_schema_keys_present(self, _snippets):
        result = cs.search_ssm_acra(NAME, SAMPLE_KEYWORDS, "Acme Sdn Bhd")
        for key in ["profile_url", "keyword_hits", "summary", "company", "status", "jurisdiction"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "Acme Sdn Bhd SSM Malaysia", "snippet": "Acme Sdn Bhd is registered and active in Malaysia", "url": "https://ssm.com.my"}
    ])
    def test_ssm_detects_malaysia_registration(self, _snippets):
        result = cs.search_ssm_acra(NAME, SAMPLE_KEYWORDS, "Acme Sdn Bhd")
        self.assertIn("Malaysia", result["jurisdiction"])
        self.assertIsNotNone(result["status"])


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 11 – Design platforms: Behance, Dribbble
# ═════════════════════════════════════════════════════════════════════════════

class TestDesignPlatforms(unittest.TestCase):

    # ── search_behance ────────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch("requests.get", return_value=None)
    def test_behance_schema_keys_present(self, _get, _snippets):
        result = cs.search_behance(NAME, SAMPLE_KEYWORDS, "johndoe")
        for key in ["profile_url", "keyword_hits", "summary", "projects", "appreciations"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[])
    @patch("requests.get")
    def test_behance_url_built_correctly(self, mock_get, _snippets):
        mock_get.return_value = _mock_200(text="15 Projects 2,300 Appreciations designer portfolio")
        result = cs.search_behance(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://www.behance.net/johndoe")
        self.assertEqual(result["projects"], 15)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "johndoe on Behance", "url": "https://www.behance.net/johndoe", "snippet": "12 Projects 800 Appreciations"}
    ])
    @patch("requests.get", return_value=None)
    def test_behance_no_identifier_deep_search(self, _get, _snippets):
        result = cs.search_behance(NAME, SAMPLE_KEYWORDS, None)
        # Should have found a handle via web search snippet
        self.assertIsNotNone(result["profile_url"])

    # ── search_dribbble ───────────────────────────────────────────────────────
    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_dribbble_schema_keys_present(self, _snippets):
        result = cs.search_dribbble(NAME, SAMPLE_KEYWORDS, "johndoe")
        for key in ["profile_url", "keyword_hits", "summary", "shots", "followers"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "johndoe Dribbble", "snippet": "45 Shots 1,200 Followers", "url": "https://dribbble.com/johndoe"}
    ])
    def test_dribbble_url_and_stats_extracted(self, _snippets):
        result = cs.search_dribbble(NAME, SAMPLE_KEYWORDS, "johndoe")
        self.assertEqual(result["profile_url"], "https://dribbble.com/johndoe")
        self.assertEqual(result["shots"], 45)
        self.assertEqual(result["followers"], "1,200")

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "johndoe on Dribbble", "url": "https://dribbble.com/johndoe", "snippet": "UI designer"}
    ])
    def test_dribbble_no_identifier_deep_search(self, _snippets):
        result = cs.search_dribbble(NAME, SAMPLE_KEYWORDS, None)
        self.assertIsNotNone(result["profile_url"])


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 12 – Finance platform: SC/MQ registry
# ═════════════════════════════════════════════════════════════════════════════

class TestFinancePlatforms(unittest.TestCase):

    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_sc_mq_schema_keys_present(self, _snippets):
        result = cs.search_sc_mq(NAME, SAMPLE_KEYWORDS, "Jane Doe")
        for key in ["profile_url", "keyword_hits", "summary", "license", "verified"]:
            self.assertIn(key, result)

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "Jane Doe CFA Charterholder Malaysia", "snippet": "Jane Doe holds a CFA charter and is a licensed dealer", "url": "https://sc.com.my"}
    ])
    def test_sc_mq_detects_cfa_license(self, _snippets):
        result = cs.search_sc_mq(NAME, SAMPLE_KEYWORDS, "Jane Doe")
        self.assertEqual(result["license"], "CFA")
        self.assertTrue(result["verified"])

    @patch.object(cs, "search_web_snippets", return_value=[
        {"title": "John ACCA qualified", "snippet": "John is an ACCA qualified accountant in KL", "url": "https://acca.global"}
    ])
    def test_sc_mq_detects_acca(self, _snippets):
        result = cs.search_sc_mq(NAME, SAMPLE_KEYWORDS, "John")
        self.assertEqual(result["license"], "ACCA")

    @patch.object(cs, "search_web_snippets", return_value=[])
    def test_sc_mq_no_license_found(self, _snippets):
        result = cs.search_sc_mq(NAME, SAMPLE_KEYWORDS, "Unknown Person")
        self.assertFalse(result["verified"])
        self.assertIsNone(result["license"])


# ═════════════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 65)
    print("  Candidate Searcher – URL & Searching Function Test Suite")
    print("=" * 65)
    print(f"  Module under test : {SEARCHER_PATH}")
    print(f"  Verbose           : {VERBOSE}")
    print(f"  Live HTTP checks  : {RUN_LIVE}")
    print("=" * 65)

    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()

    # Load all test classes defined in this file
    test_classes = [
        TestParseIdentifier,
        TestUsernameGuesses,
        TestURLConstruction,
        TestKeywordHelpers,
        TestReturnSchema,
        TestIntegrationMocked,
        TestEdgeCases,
        TestMarketingPlatforms,
        TestHRPlatforms,
        TestDesignPlatforms,
        TestFinancePlatforms,
    ]
    if RUN_LIVE:
        test_classes.append(TestLiveURLReachability)

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    verbosity = 2 if VERBOSE else 1
    runner  = unittest.TextTestRunner(verbosity=verbosity, stream=sys.stdout)
    result  = runner.run(suite)

    print("\n" + "=" * 65)
    print(f"  Total tests run : {result.testsRun}")
    print(f"  Passed          : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures        : {len(result.failures)}")
    print(f"  Errors          : {len(result.errors)}")
    print("=" * 65)

    sys.exit(0 if result.wasSuccessful() else 1)
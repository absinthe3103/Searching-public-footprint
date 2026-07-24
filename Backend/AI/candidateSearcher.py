"""
Candidate Public Profile Searcher
Sources: GitHub, LinkedIn (public), Google Scholar, ResearchGate,
         Kaggle, Dev.to, Medium, Hashnode
Outputs: JSON (full data) + CSV (requirement match matrix)

ENHANCEMENTS:
- GitHub: Added prominent_repos (high stars/recent activity) and career_indicators
- Dev.to: Added publication_frequency metrics
- Medium: Added RSS feed parsing for articles
- Hashnode: Added GraphQL API and article extraction
- ResearchGate: Added research_interests extraction
- Scholar: Enhanced with h-index and citation trends
"""

import requests
import json
import csv
import time
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# Ensure Windows terminal encoding errors never crash print statements
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import feedparser
except ImportError:
    feedparser = None

# ──────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
GITHUB_API  = "https://api.github.com"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"  # official, no login/CAPTCHA
ORCID_API   = "https://pub.orcid.org/v3.0"                        # official, no login/CAPTCHA
DELAY       = 1.2   # seconds between requests


DEBUG = False  # set to True (or use --verbose in test.py) to see why requests fail


def orcid_get(url, params=None, timeout=12):
    """Like safe_get, but ORCID's public API requires an Accept: application/json
    header, otherwise it returns XML."""
    try:
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"},
                          params=params, timeout=timeout)
        if DEBUG and not r.ok:
            print(f"    [debug] {r.status_code} for {r.url}")
        r.raise_for_status()
        return r
    except Exception as e:
        if DEBUG:
            print(f"    [debug] ORCID request failed for {url}: {e}")
        return None


def safe_get(url, params=None, timeout=12):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if DEBUG and not r.ok:
            print(f"    [debug] {r.status_code} for {r.url}")
        r.raise_for_status()
        return r
    except Exception as e:
        if DEBUG:
            print(f"    [debug] request failed for {url}: {e}")
        return None


def kw_score(text: str, keywords: list) -> dict:
    t = text.lower()
    return {kw: kw.lower() in t for kw in keywords}


def matched(hits: dict) -> list:
    return [k for k, v in hits.items() if v]


def search_web_snippets(query: str) -> list:
    """
    Perform a public search across multiple web engines (Bing -> Google -> DuckDuckGo)
    and return structured results: [{'url': ..., 'title': ..., 'snippet': ...}].
    This ensures reliability even if one engine blocks automated requests with HTTP 202/403.
    """
    encoded = quote_plus(query)
    results = []

    # 1. Try Bing
    try:
        url = f"https://www.bing.com/search?q={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        r = requests.get(url, headers=headers, timeout=8)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select("li.b_algo"):
                a = item.select_one("h2 a")
                if not a: continue
                href = a.get("href", "")
                title = a.get_text(strip=True)
                p = item.select_one("p") or item.select_one(".b_caption p")
                snippet = p.get_text(" ", strip=True) if p else ""
                results.append({"url": href, "title": title, "snippet": snippet})
    except Exception as e:
        if DEBUG: print(f"    [debug] Bing search failed: {e}")

    if results:
        return results

    # 2. Try DuckDuckGo
    try:
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select(".result"):
                a = item.select_one(".result__a")
                if not a: continue
                href = a.get("href", "")
                title = a.get_text(strip=True)
                p = item.select_one(".result__snippet")
                snippet = p.get_text(" ", strip=True) if p else ""
                results.append({"url": href, "title": title, "snippet": snippet})
    except Exception as e:
        if DEBUG: print(f"    [debug] DDG search failed: {e}")

    return results


def parse_identifier(identifier, platform: str):
    """
    Normalize a user-supplied identifier (username OR full profile URL) into
    a bare handle/username for the given platform.

    Returns None if identifier is empty/None (caller should then fall back
    to searching by name).
    """
    if not identifier:
        return None
    ident = identifier.strip()
    if not ident:
        return None

    url_patterns = {
        "github":         r"github\.com/([A-Za-z0-9\-]+)",
        "linkedin":       r"(?:[a-z0-9\-]+\.)?linkedin\.com/in/([A-Za-z0-9\-_%]+)",
        "kaggle":         r"kaggle\.com/([A-Za-z0-9\-_]+)",
        "devto":          r"dev\.to/([A-Za-z0-9\-_]+)",
        "medium":         r"medium\.com/@?([A-Za-z0-9\-_.]+)",
        "hashnode":       r"hashnode\.com/@([A-Za-z0-9\-_]+)",
        "researchgate":   r"researchgate\.net/profile/([A-Za-z0-9_\-.]+)",
        "google_scholar": r"scholar\.google\.com/citations\?user=([A-Za-z0-9_\-]+)",
        "semantic_scholar": r"semanticscholar\.org/author/[^/]+/(\d+)",
        "orcid":          r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])",
    }

    pattern = url_patterns.get(platform)
    if pattern:
        m = re.search(pattern, ident, re.I)
        if m:
            return m.group(1)

    # Not a URL we recognize for this platform (or a plain string) —
    # treat the whole thing as a handle, stripping a leading '@' if present.
    return ident.lstrip("@")


def username_guesses(name: str) -> list:
    parts = name.lower().split()
    guesses = []
    if len(parts) >= 2:
        guesses += [
            "".join(parts),
            f"{parts[0]}.{parts[-1]}",
            f"{parts[0]}{parts[-1]}",
            f"{parts[0]}-{parts[-1]}",
            f"{parts[0][0]}{parts[-1]}",
            parts[0],
            parts[-1],
        ]
    else:
        guesses.append(parts[0])
    return list(dict.fromkeys(guesses))


# ──────────────────────────────────────────────────────────
# 1. GITHUB
# ──────────────────────────────────────────────────────────
def search_github(name: str, keywords: list, identifier: str = None) -> dict:
    handle = parse_identifier(identifier, "github")
    out = {
        "profile_url": None, "bio": "", "public_repos": 0,
        "followers": 0, "last_active": None,
        "top_languages": [], "repos": [], "keyword_hits": {},
        "latest_push": None, "contribution_activity": {},
        "prominent_repos": [],
        "career_indicators": {},
        "summary": "Not found"
    }

    # ── No identifier supplied → guess usernames ──────────
    if not handle:
        print("\n[GitHub] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [GitHub] Trying guess '{g}' ...")
            p = safe_get(f"{GITHUB_API}/users/{g}")
            if p and p.status_code == 200:
                possible_urls.append(p.json().get("html_url", f"https://github.com/{g}"))
                print(f"    -> Found possible profile: {possible_urls[-1]}")
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    print(f"\n[GitHub] Trying direct username '{handle}' ...")
    p = safe_get(f"{GITHUB_API}/users/{handle}")
    if not (p and p.status_code == 200):
        print(f"  \u2717 '{handle}' not found on GitHub")
        out["summary"] = f"GitHub user '{handle}' not found"
        return out

    username = handle
    out["profile_url"] = p.json().get("html_url", f"https://github.com/{handle}")
    print(f"  \u2192 {out['profile_url']}")
    time.sleep(DELAY)

    pd = p.json()
    out["bio"]          = pd.get("bio") or ""
    out["public_repos"] = pd.get("public_repos", 0)
    out["followers"]    = pd.get("followers", 0)
    out["last_active"]  = pd.get("updated_at", "")[:10]
    out["created_at"]   = (pd.get("created_at") or "")[:10]
    time.sleep(DELAY)

    rr = safe_get(f"{GITHUB_API}/users/{username}/repos",
                  params={"sort": "pushed", "per_page": 15})
    repo_text = out["bio"]
    lang_count = {}

    if rr:
        for repo in rr.json():
            lang = repo.get("language") or ""
            if lang:
                lang_count[lang] = lang_count.get(lang, 0) + 1
            pushed_date = (repo.get("pushed_at") or "")[:10]
            stars = repo.get("stargazers_count", 0)
            info = {
                "name":        repo.get("name"),
                "description": repo.get("description") or "",
                "language":    lang,
                "stars":       stars,
                "last_push":   pushed_date,
                "url":         repo.get("html_url"),
            }
            out["repos"].append(info)
            repo_text += f" {info['name']} {info['description']} {lang}"
            is_recent = False
            if pushed_date:
                try:
                    days_since = (datetime.now() - datetime.strptime(pushed_date, "%Y-%m-%d")).days
                    is_recent = days_since < 30
                except:
                    is_recent = False
            is_high_star = stars >= 10
            if is_high_star or is_recent:
                out["prominent_repos"].append({
                    "name": info["name"],
                    "stars": stars,
                    "reason": "high-star" if is_high_star else "recently-active",
                    "url": info["url"],
                })

    out["top_languages"]  = sorted(lang_count, key=lang_count.get, reverse=True)[:5]
    out["keyword_hits"]   = kw_score(repo_text, keywords)

    recent_pushes = [repo["last_push"] for repo in out["repos"] if repo.get("last_push")]
    out["latest_push"] = max(recent_pushes, default=None) if recent_pushes else None
    out["contribution_activity"] = {
        "repo_count": len(out["repos"]),
        "public_repos": out["public_repos"],
        "followers": out["followers"],
        "total_stars": sum(repo.get("stars", 0) for repo in out["repos"]),
    }

    account_created = out.get("created_at", "")
    earliest_push = min(recent_pushes) if recent_pushes else None
    if account_created or earliest_push:
        try:
            start_date = datetime.strptime(account_created or earliest_push, "%Y-%m-%d")
            years_active = round((datetime.now() - start_date).days / 365.25, 1)
            out["career_indicators"] = {
                "github_account_created": account_created,
                "first_commit_around": earliest_push,
                "years_active_on_github": years_active,
                "estimated_tenure": f"{int(years_active)}+ years" if years_active >= 1 else "<1 year",
                "last_activity": out["latest_push"],
            }
        except:
            pass

    m = matched(out["keyword_hits"])
    out["summary"] = (
        f"Found. Languages: {out['top_languages']}. "
        f"{len(out['prominent_repos'])} prominent repos. "
        f"{len(m)}/{len(keywords)} keywords matched: {m}"
    )
    return out


# ──────────────────────────────────────────────────────────
# 2. LINKEDIN (public profile only)
# ──────────────────────────────────────────────────────────
def search_linkedin(name: str, keywords: list, identifier: str = None) -> dict:
    handle = parse_identifier(identifier, "linkedin")
    out = {
        "profile_url": None, "current_role": None,
        "company": None, "keyword_hits": {},
        "summary": "Not found",
        "linkedin_from_github": None,
    }

    # ── No identifier supplied → guess usernames ──────────
    if not handle:
        print("\n[LinkedIn] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [LinkedIn] Trying guess '{g}' ...")
            query = f'site:linkedin.com/in "{g}"'
            res = search_web_snippets(query)
            if res:
                for r in res:
                    if "linkedin.com/in/" in r["url"]:
                        possible_urls.append(r["url"])
                        print(f"    -> Found possible profile: {r['url']}")
                        break
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    slug = handle.rstrip("/")
    direct_url = f"https://www.linkedin.com/in/{slug}"
    out["profile_url"] = direct_url
    print(f"\n[LinkedIn] Identifier provided — profile URL set: {direct_url}")

    # Enrich role/company/keywords by searching web snippets for this exact slug
    query   = f'site:linkedin.com/in "{slug}"'
    results = search_web_snippets(query)
    all_text = ""
    for res in results[:5]:
        href = res["url"]
        text = f"{res['title']} {res['snippet']}"
        all_text += f" {text}"
        if "linkedin.com/in/" in href and not out["current_role"]:
            match = re.search(r"(?:Experience[:\s\-]+)?([A-Z][^|\u00b7\-\u2013\n]+?)\s+(?:at|@|\u00b7|\||\-|\u2013)\s+([A-Z][^\n\u00b7|\-\u2013]+)", text)
            if match:
                out["current_role"] = match.group(1).strip()
                out["company"]      = match.group(2).strip()

    out["keyword_hits"] = kw_score(all_text, keywords)
    m = matched(out["keyword_hits"])

    if out["profile_url"]:
        role_info = f" Role: {out['current_role']} @ {out['company']}." if out["current_role"] else ""
        out["summary"] = (
            f"Profile found at {out['profile_url']}.{role_info} "
            f"{len(m)}/{len(keywords)} keywords matched."
        )
    else:
        out["summary"] = "No LinkedIn profile found via public search"

    return out


# ──────────────────────────────────────────────────────────
# 3. PUBLICATIONS / CITATIONS  (Semantic Scholar primary, Google Scholar fallback)
# ──────────────────────────────────────────────────────────
def search_google_scholar(name: str, keywords: list, identifier: str = None) -> dict:
    """
    Searches Google Scholar / Semantic Scholar using the user-supplied identifier only.
    If no identifier is provided, the search is skipped entirely — no name-based guessing.

    Accepts:
      - A Google Scholar profile URL:  scholar.google.com/citations?user=XYZ
      - A bare Google Scholar user ID: XYZ
      - A Semantic Scholar author URL: semanticscholar.org/author/.../12345
      - A bare Semantic Scholar author ID (all digits): 12345
    """
    out = {
        "profile_url": None, "affiliation": "",
        "citations": 0, "interests": [],
        "publications": [], "keyword_hits": {},
        "summary": "Not searched",
        "h_index": 0,
        "i10_index": 0,
        "publication_years": {"earliest": None, "latest": None},
        "source_used": None,
    }

    # ── No identifier supplied → guess by name ──────────
    if not identifier or not identifier.strip():
        print("\n[Google Scholar] No identifier provided — guessing by name...")
        possible_urls = []
        try:
            from scholarly import scholarly as _scholarly
            search_query = _scholarly.search_author(name)
            first_author = next(search_query, None)
            if first_author:
                possible_urls.append(f"https://scholar.google.com/citations?user={first_author['scholar_id']}")
                print(f"    -> Found possible profile: {possible_urls[-1]}")
        except Exception as e:
            if DEBUG: print(f"    [debug] Scholar guessing failed: {e}")
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    # Parse both Semantic Scholar and Google Scholar URL patterns
    google_scholar_uid = parse_identifier(identifier, "google_scholar")
    sem_handle         = parse_identifier(identifier, "semantic_scholar")
    # Only treat as a Semantic Scholar ID if it's all digits
    if sem_handle and not sem_handle.isdigit():
        sem_handle = None

    fields = "name,affiliations,paperCount,citationCount,hIndex,papers.title,papers.year,papers.venue,papers.fieldsOfStudy,papers.url"

    # ── Path A: Google Scholar user ID → scholarly scraper ─
    if google_scholar_uid:
        print(f"\n[Google Scholar] Trying scholar_id '{google_scholar_uid}' ...")
        try:
            from scholarly import scholarly as _scholarly
            # search_author_id returns a dict directly (not a generator)
            author = _scholarly.search_author_id(google_scholar_uid)
            if author:
                author = _scholarly.fill(author, sections=["basics", "publications"])
                sid = author.get("scholar_id", google_scholar_uid)
                out["source_used"]  = "google_scholar"
                out["profile_url"]  = f"https://scholar.google.com/citations?user={sid}"
                out["affiliation"]  = author.get("affiliation", "")
                out["citations"]    = author.get("citedby", 0)
                out["h_index"]      = author.get("h_index", 0)
                out["i10_index"]    = author.get("i10_index", 0)
                out["interests"]    = author.get("interests", [])
                all_text = f"{out['affiliation']} {' '.join(out['interests'])}"
                years = []
                for pub in (author.get("publications") or [])[:10]:
                    bib  = pub.get("bib", {})
                    t    = bib.get("title", "")
                    year = bib.get("pub_year", "")
                    pub_url = pub.get("pub_url", "")
                    if not pub_url and pub.get("author_pub_id"):
                        user_id = pub["author_pub_id"].split(":")[0]
                        pub_url = f"https://scholar.google.com/citations?view_op=view_citation&hl=en&user={user_id}&citation_for_view={pub['author_pub_id']}"
                    
                    out["publications"].append({
                        "title": t, 
                        "year": year, 
                        "venue": bib.get("venue", ""),
                        "url": pub_url
                    })
                    all_text += f" {t}"
                    if year:
                        try:
                            years.append(int(year))
                        except Exception:
                            pass
                if years:
                    out["publication_years"]["earliest"] = min(years)
                    out["publication_years"]["latest"]   = max(years)
                out["keyword_hits"] = kw_score(all_text, keywords)
                m = matched(out["keyword_hits"])
                out["summary"] = (
                    f"Found via Google Scholar. {len(out['publications'])} pubs, "
                    f"{out['citations']} citations, h-index: {out['h_index']}. "
                    f"{len(m)}/{len(keywords)} keywords matched: {m}"
                )
                print(f"  → {out['profile_url']}")
                return out
        except Exception as e:
            print(f"  [Google Scholar] scholarly lookup failed: {e} - trying direct HTML fallback...")
            
            # Fallback to direct HTML scrape of scholar.google.com citation page
            try:
                scholar_url = f"https://scholar.google.com/citations?user={google_scholar_uid}&hl=en"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                r = requests.get(scholar_url, headers=headers, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    name_el = soup.select_one("#gsc_prf_in")
                    aff_el  = soup.select_one(".gsc_prf_il")
                    cit_el  = soup.select_one("#gsc_rsb_st td.gsc_rsb_std")
                    
                    out["source_used"] = "google_scholar_direct"
                    out["profile_url"] = scholar_url
                    out["affiliation"] = aff_el.get_text(strip=True) if aff_el else ""
                    if cit_el:
                        try: out["citations"] = int(cit_el.get_text(strip=True).replace(",", ""))
                        except Exception: pass
                    
                    all_text = out["affiliation"]
                    years = []
                    for p_item in soup.select(".gsc_a_tr")[:15]:
                        title_el = p_item.select_one(".gsc_a_at")
                        year_el  = p_item.select_one(".gsc_a_y")
                        t = title_el.get_text(strip=True) if title_el else ""
                        y = year_el.get_text(strip=True) if year_el else ""
                        
                        pub_url = ""
                        if title_el and title_el.has_attr("href"):
                            pub_url = "https://scholar.google.com" + title_el["href"]
                            
                        out["publications"].append({"title": t, "year": y, "venue": "", "url": pub_url})
                        all_text += f" {t}"
                        if y:
                            try: years.append(int(y))
                            except Exception: pass
                    
                    if years:
                        out["publication_years"]["earliest"] = min(years)
                        out["publication_years"]["latest"]   = max(years)
                    
                    out["keyword_hits"] = kw_score(all_text, keywords)
                    m = matched(out["keyword_hits"])
                    name_found = name_el.get_text(strip=True) if name_el else google_scholar_uid
                    out["summary"] = (
                        f"Found via Google Scholar direct page ({name_found}). {len(out['publications'])} pubs, "
                        f"{out['citations']} citations. {len(m)}/{len(keywords)} keywords matched: {m}"
                    )
                    print(f"  → {scholar_url}")
                    return out
            except Exception as html_e:
                print(f"  [Google Scholar] direct HTML scrape failed: {html_e}")
                
        time.sleep(DELAY)

    # ── Path B: Semantic Scholar numeric author ID ──────────
    if sem_handle:
        print(f"\n[Semantic Scholar] Trying direct author ID '{sem_handle}' ...")
        r = safe_get(f"{SEMANTIC_SCHOLAR_API}/author/{sem_handle}", params={"fields": fields})
        if r and r.status_code == 200:
            author_data = r.json()
            out["source_used"]  = "semantic_scholar"
            out["profile_url"]  = f"https://www.semanticscholar.org/author/-/{sem_handle}"
            out["affiliation"]  = ", ".join(author_data.get("affiliations") or [])
            out["citations"]    = author_data.get("citationCount", 0) or 0
            out["h_index"]      = author_data.get("hIndex", 0) or 0
            all_text = out["affiliation"]
            years, fields_count = [], {}
            for pub in (author_data.get("papers") or [])[:15]:
                title = pub.get("title", "")
                year  = pub.get("year")
                pub_url = pub.get("url", "")
                out["publications"].append({
                    "title": title, 
                    "year": year, 
                    "venue": pub.get("venue", ""),
                    "url": pub_url
                })
                all_text += f" {title}"
                if year: years.append(year)
                for fos in (pub.get("fieldsOfStudy") or []):
                    fields_count[fos] = fields_count.get(fos, 0) + 1
            if years:
                out["publication_years"]["earliest"] = min(years)
                out["publication_years"]["latest"]   = max(years)
            out["interests"]    = sorted(fields_count, key=fields_count.get, reverse=True)[:5]
            out["keyword_hits"] = kw_score(all_text, keywords)
            m = matched(out["keyword_hits"])
            out["summary"] = (
                f"Found via Semantic Scholar. {len(out['publications'])} pubs, "
                f"{out['citations']} citations, h-index: {out['h_index']}. "
                f"{len(m)}/{len(keywords)} keywords matched: {m}"
            )
            print(f"  \u2192 {out['profile_url']}")
            return out
        else:
            print(f"  \u2717 Semantic Scholar ID '{sem_handle}' not found")
        time.sleep(DELAY)

    out["summary"] = f"Identifier '{identifier}' not resolved on Google Scholar or Semantic Scholar"
    return out


# ──────────────────────────────────────────────────────────
# 4. RESEARCH PROFILE  (ORCID primary, ResearchGate scrape fallback)
# ──────────────────────────────────────────────────────────
def search_researchgate(name: str, keywords: list, identifier: str = None) -> dict:
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found",
        "research_interests": [],
        "interests": [],
        "publication_count": 0,
        "publications": [],
        "citations": 0,
        "verified_researcher": False,
        "affiliation": "",
        "source_used": None,
    }

    # ── No identifier supplied → guess usernames ──────────
    if not identifier or not identifier.strip():
        print("\n[ResearchGate] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [ResearchGate] Trying guess '{g}' ...")
            res = search_web_snippets(f'site:researchgate.net/profile "{g}"')
            if res:
                for r in res:
                    if "researchgate.net/profile/" in r["url"]:
                        possible_urls.append(r["url"])
                        print(f"    -> Found possible profile: {r['url']}")
                        break
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    orcid_handle     = parse_identifier(identifier, "orcid")
    rg_handle_direct = parse_identifier(identifier, "researchgate")
    is_valid_orcid   = lambda s: bool(re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", s or ""))
    raw_ident_lower  = identifier.lower()

    # Route: RG URL → scrape directly; real ORCID iD → ORCID API; plain slug → scrape
    user_supplied_rg    = "researchgate" in raw_ident_lower
    user_supplied_orcid = (not user_supplied_rg) and is_valid_orcid(orcid_handle or "")

    # ── Path A: ResearchGate URL or plain slug ───────────
    if not user_supplied_orcid:
        slug = rg_handle_direct or identifier.strip().lstrip("@")
        url  = f"https://www.researchgate.net/profile/{slug}"
        print(f"\n[ResearchGate] Trying direct profile URL '{url}' ...")
        r = safe_get(url)
        if r and r.status_code == 200:
            soup     = BeautifulSoup(r.text, "html.parser")
            page_txt = soup.get_text(" ", strip=True)
            out["profile_url"]  = url
            out["source_used"]  = "researchgate_scrape"
            out["keyword_hits"] = kw_score(page_txt, keywords)
            m = matched(out["keyword_hits"])
            out["summary"] = f"Profile found on ResearchGate. {len(m)}/{len(keywords)} keywords matched: {m}"
            print(f"  → {url}")
            try:
                interests_section = soup.find(string=re.compile("Research interests", re.I))
                if interests_section:
                    parent = interests_section.find_parent()
                    if parent:
                        interests_text = parent.get_text(" ", strip=True)
                        interests = re.findall(r"([A-Za-z ]+?)(?:,|;|$)", interests_text)
                        out["research_interests"] = [i.strip() for i in interests if len(i.strip()) > 2][:10]
                        out["interests"] = out["research_interests"]
                pub_text = re.search(r"(\d+)\s+Publication", page_txt)
                if pub_text:
                    out["publication_count"] = int(pub_text.group(1))
                if "verified researcher" in page_txt.lower() or "✓" in page_txt[:500]:
                    out["verified_researcher"] = True
            except Exception:
                pass
            return out
        else:
            print(f"  ✗ Direct GET blocked (HTTP {r.status_code if r else 'error'}) — trying search snippet fallback ...")
            # 2. Search engine snippet fallback (bypasses Cloudflare block on RG)
            snippets = search_web_snippets(f'site:researchgate.net/profile/{slug} OR "researchgate.net/profile/{slug}"')
            if snippets:
                combined_txt = " ".join([f"{s['title']} {s['snippet']}" for s in snippets])
                out["profile_url"] = url
                out["source_used"] = "researchgate_snippet"
                out["keyword_hits"] = kw_score(combined_txt, keywords)
                m = matched(out["keyword_hits"])
                out["summary"] = f"Profile verified on ResearchGate via search index. {len(m)}/{len(keywords)} keywords matched: {m}"
                print(f"  → {url} (via index)")
                return out
            # 3. Final fallback: Use Semantic Scholar API to fetch the academic footprint using the extracted name
            print(f"  [ResearchGate] Snippets failed, querying Semantic Scholar for academic footprint fallback...")
            try:
                clean_name = slug.replace("-", " ").replace("_", " ")
                sem_url = "https://api.semanticscholar.org/graph/v1/author/search"
                sem_params = {
                    "query": clean_name,
                    "fields": "name,affiliations,paperCount,papers.title,papers.url,citationCount,hIndex",
                    "limit": 1
                }
                sem_r = safe_get(sem_url, params=sem_params)
                if sem_r and sem_r.status_code == 200:
                    sem_data = sem_r.json().get("data", [])
                    if sem_data:
                        author_data = sem_data[0]
                        out["publication_count"] = author_data.get("paperCount", 0)
                        out["citations"] = author_data.get("citationCount", 0)
                        out["publications"] = author_data.get("papers") or []
                        
                        all_text = ""
                        for pub in out["publications"][:15]:
                            title = pub.get("title", "")
                            all_text += f" {title}"
                            
                        out["keyword_hits"] = kw_score(all_text, keywords)
                        m = matched(out["keyword_hits"])
                        
                        out["profile_url"] = url
                        out["source_used"] = "researchgate_unverified_semantic_scholar_fallback"
                        out["summary"] = f"Linked (details fetched via Semantic Scholar). {out['publication_count']} pubs. {len(m)}/{len(keywords)} keywords matched: {m}"
                        print(f"  → {url} (data from Semantic Scholar)")
                        return out
            except Exception as sem_e:
                print(f"  [ResearchGate] Semantic Scholar fallback failed: {sem_e}")

            out["profile_url"] = url
            out["source_used"] = "researchgate_unverified"
            out["summary"] = f"Profile linked successfully (details hidden by Cloudflare)."
            print(f"  → {url} (unverified)")
            return out

    # ── Path B: Real ORCID iD ──────────────────────────
    orcid_id = orcid_handle
    print(f"\n[ORCID] Trying direct ORCID iD '{orcid_id}' ...")
    out["profile_url"] = f"https://orcid.org/{orcid_id}"
    all_text = ""

    person_r = orcid_get(f"{ORCID_API}/{orcid_id}/person")
    if person_r:
        pd = person_r.json()
        kw_section = (pd.get("keywords") or {}).get("keyword") or []
        out["research_interests"] = [k.get("content", "") for k in kw_section][:10]
        all_text += " " + " ".join(out["research_interests"])
        out["verified_researcher"] = True

    works_r = orcid_get(f"{ORCID_API}/{orcid_id}/works")
    if works_r:
        groups = works_r.json().get("group") or []
        out["publication_count"] = len(groups)
        for g in groups[:10]:
            summary_item = (g.get("work-summary") or [{}])[0]
            title = ((summary_item.get("title") or {}).get("title") or {}).get("value", "")
            pub_url = (summary_item.get("url") or {}).get("value", "")
            out["publications"].append({"title": title, "url": pub_url})
            all_text += f" {title}"

    out["source_used"]  = "orcid"
    out["keyword_hits"] = kw_score(all_text, keywords)
    m = matched(out["keyword_hits"])
    if out["verified_researcher"]:
        out["summary"] = (
            f"Found via ORCID. {out['publication_count']} works on record. "
            f"{len(m)}/{len(keywords)} keywords matched: {m}"
        )
        print(f"  \u2192 {out['profile_url']}")
    else:
        out["summary"] = f"ORCID iD '{orcid_id}' not found in public registry"
        out["profile_url"] = None
    return out



# ──────────────────────────────────────────────────────────
# 5. KAGGLE
# ──────────────────────────────────────────────────────────
def search_kaggle(name: str, keywords: list, identifier: str = None) -> dict:
    handle = parse_identifier(identifier, "kaggle")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found",
        "competitions": 0,
        "notebooks": 0,
        "datasets": 0,
        "ranking": None,
        "pinned_works": [],
        "writeups": [],
    }

    # ── No identifier supplied → guess usernames ──────────
    if not handle:
        print("\n[Kaggle] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [Kaggle] Trying guess '{g}' ...")
            r = safe_get(f"https://www.kaggle.com/{g}")
            if r and r.status_code == 200:
                possible_urls.append(f"https://www.kaggle.com/{g}")
                print(f"    -> Found possible profile: {possible_urls[-1]}")
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    print(f"\n[Kaggle] Trying identifier '{handle}' ...")

    # Try Kaggle API first (if available and authenticated)
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        user_data = api.user_metadata(handle)
        if user_data:
            out["profile_url"] = f"https://www.kaggle.com/{handle}"
            out["competitions"] = user_data.get("competitionCount", 0)
            out["notebooks"]    = user_data.get("notebookCount", 0)
            out["datasets"]     = user_data.get("datasetCount", 0)
            out["ranking"]      = user_data.get("performanceTier", {}).get("rank", None)
            
            try:
                kernels = api.kernels_list(user=handle)
                for k in (kernels or [])[:5]:
                    if hasattr(k, "title") and hasattr(k, "ref"):
                        out["writeups"].append({"title": k.title, "url": f"https://www.kaggle.com/code/{k.ref}"})
                        
                datasets = api.datasets_list(user=handle)
                for d in (datasets or [])[:5]:
                    if hasattr(d, "title") and hasattr(d, "ref"):
                        out["pinned_works"].append({"title": d.title, "url": f"https://www.kaggle.com/{d.ref}"})
            except Exception as api_err:
                if DEBUG: print(f"    [debug] Kaggle API works/datasets fetch failed: {api_err}")

            all_text = f"{out['ranking']} competitions notebooks datasets"
            out["keyword_hits"] = kw_score(all_text, keywords)
            m = matched(out["keyword_hits"])
            out["summary"] = (
                f"Found. {out['competitions']} competitions, "
                f"{out['notebooks']} notebooks, "
                f"{out['datasets']} datasets. "
                f"{len(m)}/{len(keywords)} keywords matched."
            )
            print(f"  \u2192 {out['profile_url']}")
            return out
    except:
        pass  # Kaggle API not available, fall through to scrape

    # Scrape the profile page directly with the given identifier only
    url = f"https://www.kaggle.com/{handle}"
    r   = safe_get(url)
    if r and r.status_code == 200:
        soup     = BeautifulSoup(r.text, "html.parser")
        page_txt = soup.get_text(" ", strip=True)
        out["profile_url"]  = url
        out["keyword_hits"] = kw_score(page_txt, keywords)
        try:
            comp_match = re.search(r"(\d+)\s+(?:Competition|competitions)", page_txt)
            if comp_match: out["competitions"] = int(comp_match.group(1))
            note_match = re.search(r"(\d+)\s+(?:Notebook|notebooks)", page_txt)
            if note_match: out["notebooks"] = int(note_match.group(1))
            data_match = re.search(r"(\d+)\s+(?:Dataset|datasets)", page_txt)
            if data_match: out["datasets"] = int(data_match.group(1))
        except:
            pass
        m = matched(out["keyword_hits"])
        out["summary"] = f"Profile found at {url}. {len(m)}/{len(keywords)} keywords matched."
        print(f"  \u2192 {url}")
        return out

    out["summary"] = f"Kaggle user '{handle}' not found"
    return out


# ──────────────────────────────────────────────────────────
# 6. DEV.TO
# ──────────────────────────────────────────────────────────
def search_devto(name: str, keywords: list, identifier: str = None) -> dict:
    handle = parse_identifier(identifier, "devto")
    out = {
        "profile_url": None, "articles": [],
        "keyword_hits": {}, "summary": "Not found",
        "publication_frequency": {},
        "top_topics": [],
    }

    # ── No identifier supplied → guess usernames ──────────
    if not handle:
        print("\n[Dev.to] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [Dev.to] Trying guess '{g}' ...")
            r = safe_get(f"https://dev.to/api/articles?username={g}&per_page=1")
            if r and r.status_code == 200:
                possible_urls.append(f"https://dev.to/{g}")
                print(f"    -> Found possible profile: {possible_urls[-1]}")
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    print(f"\n[Dev.to] Trying identifier '{handle}' ...")
    r = safe_get(f"https://dev.to/api/articles?username={handle}&per_page=10")
    if r and r.status_code == 200:
        articles = r.json()
        if articles:
            out["profile_url"] = f"https://dev.to/{handle}"
            all_text = ""
            all_tags = {}
            for a in articles:
                pub_date = a.get("published_at", "")[:10]
                out["articles"].append({
                    "title":     a.get("title"),
                    "tags":      a.get("tag_list", []),
                    "reactions": a.get("positive_reactions_count", 0),
                    "published": pub_date,
                    "url":       a.get("url", ""),
                })
                all_text += f" {a.get('title','')} {' '.join(a.get('tag_list',[]))}"
                for tag in a.get("tag_list", []):
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            if articles and articles[0].get("published_at"):
                try:
                    latest = datetime.strptime(articles[0]["published_at"][:10], "%Y-%m-%d")
                    oldest = datetime.strptime(articles[-1]["published_at"][:10], "%Y-%m-%d")
                    months_active = max(1, (latest - oldest).days / 30)
                    freq_per_month = round(len(articles) / months_active, 2)
                    out["publication_frequency"] = {
                        "total_articles": len(articles),
                        "articles_per_month": freq_per_month,
                        "latest_article": articles[0]["published_at"][:10],
                        "oldest_article_shown": articles[-1]["published_at"][:10],
                    }
                except:
                    pass
            out["top_topics"] = [t for t, _ in sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:5]]
            out["keyword_hits"] = kw_score(all_text, keywords)
            m = matched(out["keyword_hits"])
            out["summary"] = (
                f"Found {len(articles)} articles at {out['profile_url']}. "
                f"Avg {out['publication_frequency'].get('articles_per_month', 'N/A')} articles/month. "
                f"{len(m)}/{len(keywords)} keywords matched: {m}"
            )
            print(f"  \u2192 {out['profile_url']}")
            return out

    out["summary"] = f"Dev.to user '{handle}' not found"
    return out


# ──────────────────────────────────────────────────────────
# 7. MEDIUM
# ──────────────────────────────────────────────────────────
def search_medium(name: str, keywords: list, identifier: str = None) -> dict:
    handle = parse_identifier(identifier, "medium")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found",
        "articles": [],
        "publication_frequency": {},
        "top_topics": [],
    }
    all_text = ""

    # ── No identifier supplied → guess usernames ──────────
    if not handle:
        print("\n[Medium] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [Medium] Trying guess '{g}' ...")
            r = safe_get(f"https://medium.com/@{g}")
            if r and r.status_code == 200:
                possible_urls.append(f"https://medium.com/@{g}")
                print(f"    -> Found possible profile: {possible_urls[-1]}")
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    candidate_url = f"https://medium.com/@{handle}"
    print(f"\n[Medium] Trying direct username '{handle}' ...")
    r_direct = safe_get(candidate_url)
    if not (r_direct and r_direct.status_code == 200):
        print(f"  \u2717 '{handle}' not found on Medium")
        out["summary"] = f"Medium user '{handle}' not found"
        return out

    out["profile_url"] = candidate_url

    # Parse RSS feed for articles and topics
    if feedparser:
        try:
            rss_url = f"https://medium.com/feed/@{handle}"
            feed = feedparser.parse(rss_url)
            all_tags = {}
            if feed.entries:
                for entry in feed.entries[:10]:
                    article_title = entry.get("title", "")
                    pub_date = entry.get("published", "")[:10] if entry.get("published") else ""
                    tags = [tag.get("term", "") for tag in entry.get("tags", [])]
                    if not tags:
                        tags = re.findall(r"#(\w+)", entry.get("summary", ""))
                    out["articles"].append({
                        "title":     article_title,
                        "published": pub_date,
                        "tags":      tags[:5],
                        "url":       entry.get("link", ""),
                    })
                    all_text += f" {article_title} {' '.join(tags)}"
                    for tag in tags:
                        all_tags[tag] = all_tags.get(tag, 0) + 1
                if len(feed.entries) > 1:
                    try:
                        latest = datetime.strptime(feed.entries[0].get("published", "")[:10], "%Y-%m-%d")
                        oldest = datetime.strptime(feed.entries[-1].get("published", "")[:10], "%Y-%m-%d")
                        months_active = max(1, (latest - oldest).days / 30)
                        freq_per_month = round(len(feed.entries) / months_active, 2)
                        out["publication_frequency"] = {
                            "total_articles": len(feed.entries),
                            "articles_per_month": freq_per_month,
                            "latest_article": feed.entries[0].get("published", "")[:10],
                        }
                    except:
                        pass
                out["top_topics"] = [t for t, _ in sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:5]]
        except Exception:
            pass

    out["keyword_hits"] = kw_score(all_text, keywords)
    m = matched(out["keyword_hits"])
    articles_info = f" {len(out['articles'])} articles found." if out["articles"] else ""
    freq_info = f" Avg {out['publication_frequency'].get('articles_per_month', 'N/A')} articles/month." if out["publication_frequency"] else ""
    out["summary"] = f"Profile found.{articles_info}{freq_info} {len(m)}/{len(keywords)} keywords matched."
    return out


# ──────────────────────────────────────────────────────────
# 8. HASHNODE
# ──────────────────────────────────────────────────────────
def search_hashnode(name: str, keywords: list, identifier: str = None) -> dict:
    handle = parse_identifier(identifier, "hashnode")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found",
        "articles": [],
        "publication_frequency": {},
        "top_topics": [],
    }

    # ── No identifier supplied → guess usernames ──────────
    if not handle:
        print("\n[Hashnode] No identifier provided — guessing...")
        guesses = username_guesses(name)
        possible_urls = []
        for g in guesses:
            print(f"  [Hashnode] Trying guess '{g}' ...")
            r = safe_get(f"https://hashnode.com/@{g}")
            if r and r.status_code == 200:
                possible_urls.append(f"https://hashnode.com/@{g}")
                print(f"    -> Found possible profile: {possible_urls[-1]}")
            time.sleep(DELAY)
        out["possible_profiles"] = possible_urls
        out["summary"] = "Not provided — guessed"
        return out

    print(f"\n[Hashnode] Trying identifier '{handle}' ...")
    r = safe_get(f"https://hashnode.com/@{handle}")
    if not (r and r.status_code == 200):
        out["summary"] = f"Hashnode user '{handle}' not found"
        return out

    soup     = BeautifulSoup(r.text, "html.parser")
    page_txt = soup.get_text(" ", strip=True)
    out["profile_url"] = f"https://hashnode.com/@{handle}"
    print(f"  \u2192 {out['profile_url']}")

    # Try GraphQL API to get articles and topics
    try:
        graphql_query = f"""
        query {{
          user(username: "{handle}") {{
            name
            username
            posts(first: 10) {{
              edges {{
                node {{
                  title
                  url
                  publishedAt
                  tags {{
                    name
                  }}
                  bookmarks {{
                    totalCount
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        gql_r = safe_get(
            "https://gql.hashnode.com/",
            params={"query": graphql_query.replace("\n", "").replace("  ", "")}
        )
        if gql_r and gql_r.status_code == 200:
            gql_data = gql_r.json().get("data", {}).get("user", {})
            posts = gql_data.get("posts", {}).get("edges", [])
            all_tags = {}
            all_text = ""
            for post_edge in posts:
                post = post_edge.get("node", {})
                title = post.get("title", "")
                pub_date = post.get("publishedAt", "")[:10] if post.get("publishedAt") else ""
                pub_url = post.get("url", "")
                tags = [tag.get("name", "") for tag in post.get("tags", [])]
                out["articles"].append({"title": title, "published": pub_date, "tags": tags, "url": pub_url})
                all_text += f" {title} {' '.join(tags)}"
                for tag in tags:
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            if len(posts) > 1:
                try:
                    latest_date = posts[0]["node"].get("publishedAt", "")[:10]
                    oldest_date = posts[-1]["node"].get("publishedAt", "")[:10]
                    if latest_date and oldest_date:
                        latest = datetime.strptime(latest_date, "%Y-%m-%d")
                        oldest = datetime.strptime(oldest_date, "%Y-%m-%d")
                        months_active = max(1, (latest - oldest).days / 30)
                        out["publication_frequency"] = {
                            "total_articles": len(posts),
                            "articles_per_month": round(len(posts) / months_active, 2),
                            "latest_article": latest_date,
                        }
                except:
                    pass
            out["top_topics"] = [t for t, _ in sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:5]]
            out["keyword_hits"] = kw_score(all_text, keywords)
    except Exception:
        out["keyword_hits"] = kw_score(page_txt, keywords)

    m = matched(out["keyword_hits"])
    out["summary"] = (
        f"Found {len(out['articles'])} articles at {out['profile_url']}. "
        f"{len(m)}/{len(keywords)} keywords matched."
    )
    return out




# ──────────────────────────────────────────────────────────
# REQUIREMENT MATCHING
# ──────────────────────────────────────────────────────────
def compute_match(requirements: list, sources: dict) -> list:
    report = []
    for req in requirements:
        req_words = [w for w in re.split(r"[\s,/+()\-]+", req.lower())
                     if len(w) > 2]
        evidence = {}
        for src, data in sources.items():
            hits = data.get("keyword_hits", {})
            found = any(
                any(rw in k.lower() for rw in req_words)
                for k, v in hits.items() if v
            )
            evidence[src] = found

        report.append({
            "requirement":           req,
            "fulfilled":             any(evidence.values()),
            "evidence":              evidence,
            "sources_with_evidence": [s for s, v in evidence.items() if v],
        })
    return report


# ──────────────────────────────────────────────────────────
# SAVE
# ──────────────────────────────────────────────────────────
def save(candidate: str, sources: dict, req_report: list):
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-z0-9]", "_", candidate.lower())

    json_path = f"candidate_{safe_name}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "candidate":         candidate,
            "searched_at":       ts,
            "sources":           sources,
            "requirement_report": req_report,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON saved: {json_path}")

    csv_path = f"candidate_{safe_name}_{ts}.csv"
    src_keys = list(sources.keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["requirement", "fulfilled"] + src_keys)
        writer.writeheader()
        for row in req_report:
            r = {"requirement": row["requirement"], "fulfilled": row["fulfilled"]}
            for s in src_keys:
                r[s] = row["evidence"].get(s, False)
            writer.writerow(r)
    print(f"✅ CSV saved: {csv_path}")

    return json_path, csv_path


# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────
STOP = {"and","or","the","of","in","with","to","a","an","is","are","has",
        "have","years","experience","knowledge","ability","skills","strong",
        "good","proficient","familiar","understanding","working","using","able"}

SOURCE_MAP = {
    "github":        ("GitHub",         "Repos, languages, contribution, last commit"),
    "linkedin":      ("LinkedIn",       "Current role, company, tenure"),
    "google_scholar":("Semantic Scholar","Publications, citations, h-index (Google Scholar as fallback)"),
    "researchgate":  ("ORCID",          "Publications, affiliation (ResearchGate scrape as fallback)"),
    "kaggle":        ("Kaggle",         "Competition ranking, notebooks, datasets"),
    "devto":         ("Dev.to",         "Technical articles, tags, publishing frequency"),
    "medium":        ("Medium",         "Technical writing, topics"),
    "hashnode":      ("Hashnode",       "Blog posts, technical topics"),
}

def main():
    print("=" * 60)
    print("   CANDIDATE PUBLIC PROFILE SEARCHER  v2")
    print("=" * 60)
    print(f"\nSources: {', '.join(v[0] for v in SOURCE_MAP.values())}\n")

    name = input("Candidate full name: ").strip()
    if not name:
        sys.exit("❌ Name cannot be empty.")

    print("\nOptional: paste a specific username or profile URL for any platform.")
    print("Leave blank to search by full name instead.\n")
    identifiers = {}
    for key, (label, _) in SOURCE_MAP.items():
        val = input(f"  {label} username/URL (optional): ").strip()
        identifiers[key] = val or None

    print("\nJob requirements (one per line, blank line to finish):\n")
    requirements = []
    while True:
        line = input(f"  Req {len(requirements)+1}: ").strip()
        if not line:
            if requirements: break
        else:
            requirements.append(line)

    # Extract search keywords
    kws = []
    for req in requirements:
        for w in re.split(r"[\s,/+()\-]+", req.lower()):
            if w and w not in STOP and len(w) > 2:
                kws.append(w)
    kws = list(dict.fromkeys(kws))
    print(f"\n🔍 Keywords extracted: {kws}")
    print(f"\n{'─'*60}\nSearching: {name}\n{'─'*60}")

    sources = {}
    sources["github"]         = search_github(name, kws, identifiers["github"]);                 time.sleep(DELAY)
    sources["linkedin"]       = search_linkedin(name, kws, identifiers["linkedin"]);               time.sleep(DELAY)
    sources["google_scholar"] = search_google_scholar(name, kws, identifiers["google_scholar"]);   time.sleep(DELAY)
    sources["researchgate"]   = search_researchgate(name, kws, identifiers["researchgate"]);       time.sleep(DELAY)
    sources["kaggle"]         = search_kaggle(name, kws, identifiers["kaggle"]);                   time.sleep(DELAY)
    sources["devto"]          = search_devto(name, kws, identifiers["devto"]);                     time.sleep(DELAY)
    sources["medium"]         = search_medium(name, kws, identifiers["medium"]);                   time.sleep(DELAY)
    sources["hashnode"]       = search_hashnode(name, kws, identifiers["hashnode"])

    req_report = compute_match(requirements, sources)

    # ── Print report ──
    print(f"\n{'='*60}")
    print("  REQUIREMENT MATCH REPORT")
    print(f"{'='*60}")
    for item in req_report:
        icon = "✅" if item["fulfilled"] else "❌"
        srcs = ", ".join(item["sources_with_evidence"]) or "—"
        print(f"\n{icon} {item['requirement']}")
        print(f"   └─ Evidence in: {srcs}")

    fulfilled = sum(1 for i in req_report if i["fulfilled"])
    print(f"\n{'─'*60}")
    print(f"Overall: {fulfilled}/{len(requirements)} requirements have public evidence")

    # ── Source summary ──
    print(f"\n{'─'*60}")
    print("  SOURCE SUMMARY")
    print(f"{'─'*60}")
    for key, data in sources.items():
        label = SOURCE_MAP[key][0]
        url   = data.get("profile_url") or "—"
        print(f"  {label:<18} {url}")

    save(name, sources, req_report)

if __name__ == "__main__":
    main()
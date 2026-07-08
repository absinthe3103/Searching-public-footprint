"""
Candidate Public Profile Searcher
Sources: GitHub, LinkedIn (public), Google Scholar, ResearchGate,
         Kaggle, Dev.to, Medium, Hashnode
Outputs: JSON (full data) + CSV (requirement match matrix)
"""

import requests
import json
import csv
import time
import re
import sys
from datetime import datetime
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

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
DELAY       = 1.2   # seconds between requests


def safe_get(url, params=None, timeout=12):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


def kw_score(text: str, keywords: list) -> dict:
    t = text.lower()
    return {kw: kw.lower() in t for kw in keywords}


def matched(hits: dict) -> list:
    return [k for k, v in hits.items() if v]


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
def search_github(name: str, keywords: list) -> dict:
    print(f"\n[GitHub] Searching '{name}' ...")
    out = {
        "profile_url": None, "bio": "", "public_repos": 0,
        "followers": 0, "last_active": None,
        "top_languages": [], "repos": [], "keyword_hits": {},
        "summary": "Not found"
    }

    r = safe_get(f"{GITHUB_API}/search/users", params={"q": name, "per_page": 5})
    if not r:
        out["summary"] = "API error / rate limited"; return out

    items = r.json().get("items", [])
    if not items:
        out["summary"] = "No GitHub user found"; return out

    user     = items[0]
    username = user["login"]
    out["profile_url"] = user["html_url"]
    print(f"  → {username}  {user['html_url']}")
    time.sleep(DELAY)

    p = safe_get(f"{GITHUB_API}/users/{username}")
    if p:
        pd = p.json()
        out["bio"]          = pd.get("bio") or ""
        out["public_repos"] = pd.get("public_repos", 0)
        out["followers"]    = pd.get("followers", 0)
        out["last_active"]  = pd.get("updated_at", "")[:10]
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
            info = {
                "name":        repo.get("name"),
                "description": repo.get("description") or "",
                "language":    lang,
                "stars":       repo.get("stargazers_count", 0),
                "last_push":   (repo.get("pushed_at") or "")[:10],
                "url":         repo.get("html_url"),
            }
            out["repos"].append(info)
            repo_text += f" {info['name']} {info['description']} {lang}"

    out["top_languages"]  = sorted(lang_count, key=lang_count.get, reverse=True)[:5]
    out["keyword_hits"]   = kw_score(repo_text, keywords)
    m = matched(out["keyword_hits"])
    out["summary"] = (
        f"Found. Languages: {out['top_languages']}. "
        f"{len(m)}/{len(keywords)} keywords matched: {m}"
    )
    return out


# ──────────────────────────────────────────────────────────
# 2. LINKEDIN (public profile only)
# ──────────────────────────────────────────────────────────
def search_linkedin(name: str, keywords: list) -> dict:
    print(f"\n[LinkedIn] Searching '{name}' (public only) ...")
    out = {
        "profile_url": None, "current_role": None,
        "company": None, "keyword_hits": {},
        "summary": "Not found"
    }

    query = f'site:linkedin.com/in "{name}"'
    url   = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    r     = safe_get(url)
    if not r:
        out["summary"] = "Search failed"; return out

    soup  = BeautifulSoup(r.text, "html.parser")
    links = soup.select(".result__a")
    all_text = ""
    for a in links[:5]:
        href = a.get("href", "")
        text = a.get_text(strip=True)
        all_text += f" {text}"
        if "linkedin.com/in/" in href and not out["profile_url"]:
            out["profile_url"] = href
            print(f"  → {href}")
            # Try to parse role/company from snippet
            parent  = a.find_parent("div", class_="result__body") or a.find_parent()
            snippet = parent.get_text(" ", strip=True) if parent else text
            # Heuristic: "Title at Company" or "Title | Company"
            match = re.search(r"([A-Z][^|·\n]+?)\s+(?:at|@|·|\|)\s+([A-Z][^\n·|]+)", snippet)
            if match:
                out["current_role"] = match.group(1).strip()
                out["company"]      = match.group(2).strip()

    out["keyword_hits"] = kw_score(all_text, keywords)
    m = matched(out["keyword_hits"])
    out["summary"] = (
        f"Profile hint found. Role: {out['current_role']} @ {out['company']}. "
        f"{len(m)}/{len(keywords)} keywords matched."
        if out["profile_url"] else "No LinkedIn profile found via public search"
    )
    return out


# ──────────────────────────────────────────────────────────
# 3. GOOGLE SCHOLAR
# ──────────────────────────────────────────────────────────
def search_google_scholar(name: str, keywords: list) -> dict:
    print(f"\n[Google Scholar] Searching '{name}' ...")
    out = {
        "profile_url": None, "affiliation": "",
        "citations": 0, "interests": [],
        "publications": [], "keyword_hits": {},
        "summary": "Not found"
    }
    try:
        from scholarly import scholarly
        author = next(scholarly.search_author(name), None)
        if not author:
            out["summary"] = "No Google Scholar profile found"; return out

        author = scholarly.fill(author, sections=["basics", "publications"])
        sid    = author.get("scholar_id", "")
        out["profile_url"]  = f"https://scholar.google.com/citations?user={sid}"
        out["affiliation"]  = author.get("affiliation", "")
        out["citations"]    = author.get("citedby", 0)
        out["interests"]    = author.get("interests", [])
        all_text = f"{out['affiliation']} {' '.join(out['interests'])}"

        for pub in (author.get("publications") or [])[:10]:
            bib = pub.get("bib", {})
            t   = bib.get("title", "")
            out["publications"].append({
                "title": t,
                "year":  bib.get("pub_year", ""),
                "venue": bib.get("venue", ""),
            })
            all_text += f" {t}"

        out["keyword_hits"] = kw_score(all_text, keywords)
        m = matched(out["keyword_hits"])
        out["summary"] = (
            f"Found. {len(out['publications'])} pubs, {out['citations']} citations. "
            f"{len(m)}/{len(keywords)} keywords matched: {m}"
        )
        print(f"  → {out['profile_url']}")
    except Exception as e:
        out["summary"] = f"Error: {str(e)[:120]}"
    return out


# ──────────────────────────────────────────────────────────
# 4. RESEARCHGATE
# ──────────────────────────────────────────────────────────
def search_researchgate(name: str, keywords: list) -> dict:
    print(f"\n[ResearchGate] Searching '{name}' ...")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found"
    }

    slug = "-".join(name.split())
    url  = f"https://www.researchgate.net/profile/{slug}"
    r    = safe_get(url)
    if r and r.status_code == 200:
        soup     = BeautifulSoup(r.text, "html.parser")
        page_txt = soup.get_text(" ", strip=True)
        if name.split()[0].lower() in page_txt.lower():
            out["profile_url"]  = url
            out["keyword_hits"] = kw_score(page_txt, keywords)
            m = matched(out["keyword_hits"])
            out["summary"] = (
                f"Profile found. {len(m)}/{len(keywords)} keywords matched: {m}"
            )
            print(f"  → {url}")
            return out

    # Fallback: DuckDuckGo
    time.sleep(DELAY)
    q  = f'site:researchgate.net "{name}"'
    r2 = safe_get(f"https://html.duckduckgo.com/html/?q={quote_plus(q)}")
    if r2:
        soup = BeautifulSoup(r2.text, "html.parser")
        for a in soup.select(".result__a")[:3]:
            href = a.get("href", "")
            if "researchgate.net/profile" in href:
                out["profile_url"] = href
                out["summary"]     = f"Profile hint found via search: {href}"
                print(f"  → {href}")
                return out

    out["summary"] = "No ResearchGate profile found"
    return out


# ──────────────────────────────────────────────────────────
# 5. KAGGLE
# ──────────────────────────────────────────────────────────
def search_kaggle(name: str, keywords: list) -> dict:
    print(f"\n[Kaggle] Searching '{name}' ...")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found"
    }

    for uname in username_guesses(name):
        url = f"https://www.kaggle.com/{uname}"
        r   = safe_get(url)
        if r and r.status_code == 200:
            soup     = BeautifulSoup(r.text, "html.parser")
            page_txt = soup.get_text(" ", strip=True)
            if name.split()[0].lower() in page_txt.lower():
                out["profile_url"]  = url
                out["keyword_hits"] = kw_score(page_txt, keywords)
                m = matched(out["keyword_hits"])
                out["summary"] = (
                    f"Profile found at {url}. "
                    f"{len(m)}/{len(keywords)} keywords matched: {m}"
                )
                print(f"  → {url}")
                return out
        time.sleep(0.6)

    out["summary"] = "No Kaggle profile found"
    return out


# ──────────────────────────────────────────────────────────
# 6. DEV.TO
# ──────────────────────────────────────────────────────────
def search_devto(name: str, keywords: list) -> dict:
    print(f"\n[Dev.to] Searching '{name}' ...")
    out = {
        "profile_url": None, "articles": [],
        "keyword_hits": {}, "summary": "Not found"
    }

    for uname in username_guesses(name):
        r = safe_get(f"https://dev.to/api/articles?username={uname}&per_page=10")
        if r and r.status_code == 200:
            articles = r.json()
            if articles:
                out["profile_url"] = f"https://dev.to/{uname}"
                all_text = ""
                for a in articles:
                    out["articles"].append({
                        "title":       a.get("title"),
                        "tags":        a.get("tag_list", []),
                        "reactions":   a.get("positive_reactions_count", 0),
                        "published":   a.get("published_at", "")[:10],
                    })
                    all_text += f" {a.get('title','')} {' '.join(a.get('tag_list',[]))}"
                out["keyword_hits"] = kw_score(all_text, keywords)
                m = matched(out["keyword_hits"])
                out["summary"] = (
                    f"Found {len(articles)} articles at {out['profile_url']}. "
                    f"{len(m)}/{len(keywords)} keywords matched: {m}"
                )
                print(f"  → {out['profile_url']}")
                return out
        time.sleep(0.5)

    out["summary"] = "No Dev.to profile found"
    return out


# ──────────────────────────────────────────────────────────
# 7. MEDIUM
# ──────────────────────────────────────────────────────────
def search_medium(name: str, keywords: list) -> dict:
    print(f"\n[Medium] Searching '{name}' ...")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found"
    }

    q  = f'site:medium.com "{name}"'
    r  = safe_get(f"https://html.duckduckgo.com/html/?q={quote_plus(q)}")
    if not r:
        out["summary"] = "Search failed"; return out

    soup     = BeautifulSoup(r.text, "html.parser")
    all_text = ""
    for a in soup.select(".result__a")[:6]:
        href = a.get("href", "")
        text = a.get_text(strip=True)
        all_text += f" {text}"
        if "medium.com/@" in href and not out["profile_url"]:
            out["profile_url"] = href
            print(f"  → {href}")

    out["keyword_hits"] = kw_score(all_text, keywords)
    m = matched(out["keyword_hits"])
    out["summary"] = (
        f"Profile hint found. {len(m)}/{len(keywords)} keywords matched."
        if out["profile_url"] else "No Medium profile found via search"
    )
    return out


# ──────────────────────────────────────────────────────────
# 8. HASHNODE
# ──────────────────────────────────────────────────────────
def search_hashnode(name: str, keywords: list) -> dict:
    print(f"\n[Hashnode] Searching '{name}' ...")
    out = {
        "profile_url": None, "keyword_hits": {},
        "summary": "Not found"
    }

    for uname in username_guesses(name):
        r = safe_get(f"https://hashnode.com/@{uname}")
        if r and r.status_code == 200:
            soup     = BeautifulSoup(r.text, "html.parser")
            page_txt = soup.get_text(" ", strip=True)
            if name.split()[0].lower() in page_txt.lower():
                out["profile_url"]  = f"https://hashnode.com/@{uname}"
                out["keyword_hits"] = kw_score(page_txt, keywords)
                m = matched(out["keyword_hits"])
                out["summary"] = (
                    f"Profile found. {len(m)}/{len(keywords)} keywords matched: {m}"
                )
                print(f"  → {out['profile_url']}")
                return out
        time.sleep(0.5)

    out["summary"] = "No Hashnode profile found"
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
    "google_scholar":("Google Scholar", "Publications, citations, research topics"),
    "researchgate":  ("ResearchGate",   "Papers, co-authors, research profile"),
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
    sources["github"]         = search_github(name, kws);         time.sleep(DELAY)
    sources["linkedin"]       = search_linkedin(name, kws);       time.sleep(DELAY)
    sources["google_scholar"] = search_google_scholar(name, kws); time.sleep(DELAY)
    sources["researchgate"]   = search_researchgate(name, kws);   time.sleep(DELAY)
    sources["kaggle"]         = search_kaggle(name, kws);         time.sleep(DELAY)
    sources["devto"]          = search_devto(name, kws);          time.sleep(DELAY)
    sources["medium"]         = search_medium(name, kws);         time.sleep(DELAY)
    sources["hashnode"]       = search_hashnode(name, kws)

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
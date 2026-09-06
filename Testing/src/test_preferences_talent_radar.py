import argparse
import sys
import os
import requests

# Make db.py importable directly, same convention as Test.py uses for
# candidateSearcher.py. Only needed for --seed-candidates.
_HERE = os.path.dirname(os.path.abspath(__file__))
_LEGACY_DB = os.path.abspath(os.path.join(_HERE, "../../Backend/database"))
for _candidate_path in (_HERE, _LEGACY_DB):
    if os.path.isdir(_candidate_path) and _candidate_path not in sys.path:
        sys.path.insert(0, _candidate_path)

DEFAULT_API_URL = "http://localhost:8000"
TEST_UNIVERSITY_NAME = "__TEST_UNIVERSITY__"
TEST_CANDIDATE_PREFIX = "__TEST__"

CULTURE_DIMENSIONS = [
    "innovation_risk_taking", "attention_to_detail", "outcome_orientation",
    "people_orientation", "team_orientation", "aggressiveness", "stability",
]


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────
def check(label: str, condition: bool, detail: str = "") -> dict:
    status = "[OK]" if condition else "[FAIL]"
    line = f"  {status} {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return {"label": label, "passed": condition, "detail": detail}


def section(title: str):
    print(f"\n{'-'*70}")
    print(f"  {title}")
    print(f"{'-'*70}")


# ──────────────────────────────────────────────────────────
# Culture preferences tests
# ──────────────────────────────────────────────────────────
def test_culture_preferences(api: str, results: list):
    section("CULTURE PREFERENCES  (GET/PUT /preferences/culture)")

    # 1. Read current state so we can restore it afterward
    r = requests.get(f"{api}/preferences/culture", timeout=10)
    results.append(check("GET /preferences/culture returns 200", r.status_code == 200))
    if r.status_code != 200:
        print("  Cannot continue culture tests — skipping.")
        return
    original = r.json()
    results.append(check(
        "Response has all 7 known dimension keys",
        all(d in original for d in CULTURE_DIMENSIONS),
        f"got keys: {list(original.keys())}",
    ))
    results.append(check(
        "All values are booleans",
        all(isinstance(v, bool) for v in original.values()),
    ))

    # 2. Set a known test selection and verify it's reflected back
    test_selection = ["team_orientation", "stability"]
    r = requests.put(f"{api}/preferences/culture", json={"selected": test_selection}, timeout=10)
    results.append(check("PUT with valid selection returns 200", r.status_code == 200))
    if r.status_code == 200:
        updated = r.json()
        expected_on = set(test_selection)
        actually_on = {k for k, v in updated.items() if v}
        results.append(check(
            "Only the requested dimensions are ON after PUT",
            actually_on == expected_on,
            f"expected {expected_on}, got {actually_on}",
        ))

    # 3. Invalid dimension key should be rejected, not silently accepted
    r = requests.put(f"{api}/preferences/culture", json={"selected": ["not_a_real_dimension"]}, timeout=10)
    results.append(check(
        "PUT with an unknown dimension key returns 400",
        r.status_code == 400,
        f"got {r.status_code}",
    ))

    # 4. Restore original state
    original_on = [k for k, v in original.items() if v]
    r = requests.put(f"{api}/preferences/culture", json={"selected": original_on}, timeout=10)
    results.append(check(
        "Original culture selection restored",
        r.status_code == 200 and {k for k, v in r.json().items() if v} == set(original_on),
    ))


# ──────────────────────────────────────────────────────────
# Preferred universities tests
# ──────────────────────────────────────────────────────────
def test_preferred_universities(api: str, results: list):
    section("PREFERRED UNIVERSITIES  (GET/POST/DELETE /preferences/universities)")

    r = requests.get(f"{api}/preferences/universities", timeout=10)
    results.append(check("GET /preferences/universities returns 200", r.status_code == 200))
    if r.status_code != 200:
        print("  Cannot continue university tests — skipping.")
        return
    before = r.json()
    results.append(check("Response is a list", isinstance(before, list)))

    # Clean up any leftover test university from a previous interrupted run
    leftover = [u for u in before if u["name"] == TEST_UNIVERSITY_NAME]
    for u in leftover:
        requests.delete(f"{api}/preferences/universities/{u['id']}", timeout=10)

    # 1. Add a uniquely-named test university
    r = requests.post(f"{api}/preferences/universities", json={"name": TEST_UNIVERSITY_NAME}, timeout=10)
    results.append(check("POST new university returns 200", r.status_code == 200))
    new_id = None
    if r.status_code == 200:
        created = r.json()
        new_id = created.get("id")
        results.append(check(
            "Created university has id, name, created_at",
            all(k in created for k in ("id", "name", "created_at")),
        ))
        results.append(check("Created university name matches", created.get("name") == TEST_UNIVERSITY_NAME))

    # 2. Duplicate name should be rejected
    r = requests.post(f"{api}/preferences/universities", json={"name": TEST_UNIVERSITY_NAME}, timeout=10)
    results.append(check("POST duplicate name returns 409", r.status_code == 409, f"got {r.status_code}"))

    # 3. It should now appear in the list
    r = requests.get(f"{api}/preferences/universities", timeout=10)
    names_now = [u["name"] for u in r.json()] if r.status_code == 200 else []
    results.append(check("New university appears in GET list", TEST_UNIVERSITY_NAME in names_now))

    # 4. Delete it and confirm it's gone
    if new_id is not None:
        r = requests.delete(f"{api}/preferences/universities/{new_id}", timeout=10)
        results.append(check("DELETE existing university returns 200", r.status_code == 200))

        r = requests.delete(f"{api}/preferences/universities/{new_id}", timeout=10)
        results.append(check("DELETE already-removed university returns 404", r.status_code == 404, f"got {r.status_code}"))

    r = requests.get(f"{api}/preferences/universities", timeout=10)
    names_after = [u["name"] for u in r.json()] if r.status_code == 200 else []
    results.append(check(
        "Original university list unchanged after cleanup",
        sorted(names_after) == sorted([u["name"] for u in before]),
    ))


# ──────────────────────────────────────────────────────────
# Talent Radar / prioritized sorting tests
# ──────────────────────────────────────────────────────────
def seed_test_candidates(api: str, results: list) -> list:
    try:
        import db
    except ImportError as e:
        print(f"  [FAIL] Could not import db.py directly ({e}) — "
              f"run this script from Testing/src with the normal project layout, "
              f"or skip --seed-candidates.")
        return [], [], [], []

    section("SEEDING TEST CANDIDATES  (direct db.py insert, not via /evaluate)")

    # Set a known preference state for this check, remembering the original
    r = requests.get(f"{api}/preferences/culture", timeout=10)
    original_culture = [k for k, v in r.json().items() if v] if r.status_code == 200 else []
    r = requests.get(f"{api}/preferences/universities", timeout=10)
    original_unis = r.json() if r.status_code == 200 else []

    requests.put(f"{api}/preferences/culture", json={"selected": ["team_orientation"]}, timeout=10)
    requests.post(f"{api}/preferences/universities", json={"name": "__TEST_SORT_UNI__"}, timeout=10)

    seeded_ids = []
    seed_specs = [
        # name, role_domain_relevance, university, culture_fit_dimensions, expect preference_match
        (f"{TEST_CANDIDATE_PREFIX}UniOnly",     50, "__TEST_SORT_UNI__", [],                    True),
        (f"{TEST_CANDIDATE_PREFIX}CultureOnly", 60, "Other Uni",         ["team_orientation"],  True),
        (f"{TEST_CANDIDATE_PREFIX}NoMatch",     95, "Other Uni",         ["aggressiveness"],    False),
        (f"{TEST_CANDIDATE_PREFIX}Both",        40, "__TEST_SORT_UNI__", ["team_orientation"],  True),
    ]
    for name, rdr, uni, culture, _expect in seed_specs:
        cid = db.insert_candidate(
            name=name,
            dimensions={"role_domain_relevance": rdr},
            university=uni,
            culture_fit_dimensions=culture,
            status="Watch",
        )
        seeded_ids.append(cid)
    results.append(check(f"Seeded {len(seeded_ids)} deterministic test candidates", len(seeded_ids) == len(seed_specs)))

    return seeded_ids, original_culture, original_unis, seed_specs


def cleanup_seeded_candidates(api: str, seeded_ids: list, original_culture: list,
                              original_unis: list, results: list):
    try:
        import db
    except ImportError:
        return
    for cid in seeded_ids:
        db.delete_candidate(cid)
    results.append(check(f"Removed {len(seeded_ids)} seeded test candidates", True))

    # Remove the temporary test university, restore original preferences
    r = requests.get(f"{api}/preferences/universities", timeout=10)
    for u in (r.json() if r.status_code == 200 else []):
        if u["name"] == "__TEST_SORT_UNI__":
            requests.delete(f"{api}/preferences/universities/{u['id']}", timeout=10)
    requests.put(f"{api}/preferences/culture", json={"selected": original_culture}, timeout=10)
    results.append(check("Preferences restored after Talent Radar seeding", True))


def test_talent_radar(api: str, results: list, do_seed: bool):
    section("TALENT RADAR  (GET /candidates/prioritized)")

    r = requests.get(f"{api}/candidates/prioritized", timeout=10)
    results.append(check("GET /candidates/prioritized returns 200", r.status_code == 200))
    if r.status_code != 200:
        print("  Cannot continue Talent Radar tests — skipping.")
        return
    candidates = r.json()
    results.append(check("Response is a list", isinstance(candidates, list)))

    if candidates:
        sample = candidates[0]
        results.append(check(
            "Each candidate has university_match / matched_culture_dimensions / preference_match",
            all(k in sample for k in ("university_match", "matched_culture_dimensions", "preference_match")),
        ))
        match_flags = [c["preference_match"] for c in candidates]
        # Once a False appears, no True should appear after it (stable "matches float to top")
        first_false = next((i for i, v in enumerate(match_flags) if not v), None)
        ok = first_false is None or all(not v for v in match_flags[first_false:])
        results.append(check("All preference_match=True candidates appear before any False", ok))
    else:
        print("  (No candidates in the database yet — field/order checks skipped. "
              "Use --seed-candidates to verify matching logic directly.)")

    if do_seed:
        seeded_ids, original_culture, original_unis, seed_specs = seed_test_candidates(api, results)
        try:
            r = requests.get(f"{api}/candidates/prioritized", timeout=10)
            all_candidates = r.json() if r.status_code == 200 else []
            by_name = {c["name"]: c for c in all_candidates}

            for name, _rdr, _uni, _culture, expect_match in seed_specs:
                c = by_name.get(name)
                results.append(check(f"Seeded candidate '{name}' present in prioritized list", c is not None))
                if c:
                    results.append(check(
                        f"'{name}' preference_match == {expect_match}",
                        c["preference_match"] == expect_match,
                        f"got {c['preference_match']}",
                    ))

            # Within the matched group, original role_domain_relevance order
            # should be preserved (Both=40 comes after CultureOnly=60/UniOnly=50
            # in that relative order, since higher score sorts first)
            matched_names_in_order = [c["name"] for c in all_candidates
                                       if c["name"].startswith(TEST_CANDIDATE_PREFIX) and c["preference_match"]]
            expected_order = [f"{TEST_CANDIDATE_PREFIX}CultureOnly",
                              f"{TEST_CANDIDATE_PREFIX}UniOnly",
                              f"{TEST_CANDIDATE_PREFIX}Both"]
            results.append(check(
                "Matched seeded candidates keep score order within the matched group",
                matched_names_in_order == expected_order,
                f"got {matched_names_in_order}",
            ))
        finally:
            cleanup_seeded_candidates(api, seeded_ids, original_culture, original_unis, results)


# ──────────────────────────────────────────────────────────
# Restore-only mode (manual recovery from an interrupted run)
# ──────────────────────────────────────────────────────────
def restore_only(api: str, culture_csv: str, universities_csv: str):
    print("=" * 70)
    print("  RESTORE-ONLY MODE")
    print("=" * 70)
    culture = [c.strip() for c in culture_csv.split(",") if c.strip()] if culture_csv else []
    r = requests.put(f"{api}/preferences/culture", json={"selected": culture}, timeout=10)
    print(f"  Culture restored to {culture}: {'OK' if r.status_code == 200 else 'FAILED — ' + str(r.status_code)}")

    if universities_csv:
        wanted = [u.strip() for u in universities_csv.split(",") if u.strip()]
        r = requests.get(f"{api}/preferences/universities", timeout=10)
        current = {u["name"] for u in r.json()} if r.status_code == 200 else set()
        for name in wanted:
            if name not in current:
                requests.post(f"{api}/preferences/universities", json={"name": name}, timeout=10)
        print(f"  Ensured universities present: {wanted}")


# ──────────────────────────────────────────────────────────
# Summary + main
# ──────────────────────────────────────────────────────────
def print_summary(results: list):
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    for r in results:
        if not r["passed"]:
            print(f"  [FAIL] {r['label']}" + (f" — {r['detail']}" if r["detail"] else ""))
    print(f"\n  {passed}/{total} checks passed")
    if passed == total:
        print("  [OK] All checks passed.")
    return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Test Preferences and Talent Radar endpoints against a running backend."
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL,
                        help=f"Backend base URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--seed-candidates", action="store_true",
                        help="Also insert deterministic test candidates directly via db.py "
                             "to verify Talent Radar sorting/matching (cleaned up automatically).")
    parser.add_argument("--restore-only", action="store_true",
                        help="Skip all tests — just push a known culture/university state. "
                             "Use this to recover if a previous run was interrupted.")
    parser.add_argument("--restore-culture", default="",
                        help="Comma-separated dimension keys to restore (with --restore-only)")
    parser.add_argument("--restore-universities", default="",
                        help="Comma-separated university names to ensure exist (with --restore-only)")
    args = parser.parse_args()

    if args.restore_only:
        restore_only(args.api_url, args.restore_culture, args.restore_universities)
        return

    print("=" * 70)
    print("   PREFERENCES & TALENT RADAR — API TEST")
    print("=" * 70)
    print(f"  Backend: {args.api_url}")
    print(f"  Seed test candidates: {args.seed_candidates}")

    try:
        r = requests.get(f"{args.api_url}/", timeout=5)
        if r.status_code != 200:
            print(f"\n[FAIL] Backend did not respond with 200 at {args.api_url}/ — is it running?")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n[FAIL] Could not connect to {args.api_url} — start the backend first "
              f"(uvicorn Logic:app --reload --port 8000).")
        sys.exit(1)

    results = []
    test_culture_preferences(args.api_url, results)
    test_preferred_universities(args.api_url, results)
    test_talent_radar(args.api_url, results, do_seed=args.seed_candidates)

    all_passed = print_summary(results)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
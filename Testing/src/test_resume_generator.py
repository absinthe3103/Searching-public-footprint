import pytest
import requests
import sqlite3
import os
import json

# Ensure the backend is running on this port before testing
API_URL = "http://localhost:8000"

# Path to the backend SQLite DB
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Backend/database/candidates.db"))

def setup_mock_interview():
    """Injects a fake completed interview into the DB for testing."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interviews (title, candidate_name, status, transcript_text) 
        VALUES (
            'Mock SWE Interview', 
            'Alice Tester', 
            'COMPLETED', 
            'Hi, my name is Alice Tester. I am currently pursuing a Bachelors in Computer Science at University of Malaya, expecting to graduate in July 2026 with a CGPA of 3.90. In my spare time, I built an AI resume generator using React and Python FastAPI. I am highly proficient in Python, TypeScript, and Docker. Last year, I also won 1st place in the National Hackathon.'
        )
    ''')
    interview_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return interview_id

def teardown_mock_interview(interview_id):
    """Cleans up the fake interview from the DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM interviews WHERE id = ?', (interview_id,))
    conn.commit()
    conn.close()


def test_generate_cv_success():
    """Test that a valid transcript correctly generates a structured CV JSON."""
    interview_id = setup_mock_interview()
    try:
        res = requests.post(f"{API_URL}/interviews/generate-cv", json={"interview_id": interview_id}, timeout=60)
        
        # 1. Check HTTP Status
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        print("\n\n=== GENERATED CV JSON ===")
        print(json.dumps(data, indent=2))
        print("=========================\n")
        
        # 2. Check strict JSON schema adherence
        assert "name" in data, "CV JSON is missing the 'name' field"
        assert "education" in data, "CV JSON is missing the 'education' field"
        assert "projects" in data, "CV JSON is missing the 'projects' field"
        assert "technical_skills" in data, "CV JSON is missing 'technical_skills'"
        assert "academic_awards" in data, "CV JSON is missing 'academic_awards'"
        
        # 3. Check LLM extraction accuracy based on the mock transcript
        assert "Alice Tester" in data["name"]
        assert len(data["education"]) > 0
        assert "Malaya" in data["education"][0]["institution"]
        assert "3.90" in str(data["education"][0]["cgpa"])
        assert len(data["projects"]) > 0
        assert "Python" in data["technical_skills"]["languages"]
        
    finally:
        teardown_mock_interview(interview_id)


def test_generate_cv_not_found():
    """Test error handling for a non-existent interview."""
    res = requests.post(f"{API_URL}/interviews/generate-cv", json={"interview_id": 999999})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_generate_cv_no_transcript():
    """Test error handling for an interview that has no transcript (not completed)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO interviews (title, candidate_name, status) VALUES ('No Transcript', 'Ghost', 'SCHEDULED')")
    interview_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    try:
        res = requests.post(f"{API_URL}/interviews/generate-cv", json={"interview_id": interview_id})
        assert res.status_code == 400
        assert "no transcript" in res.json()["detail"].lower()
    finally:
        teardown_mock_interview(interview_id)

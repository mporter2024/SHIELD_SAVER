"""
Automated API Test Script for the Event Planner Backend
-------------------------------------------------------

This script sends HTTP requests to your Flask app and verifies that
each endpoint responds correctly.

Usage:
1️⃣ Run your Flask app (in a separate terminal):
    py app.py

2️⃣ Run this script:
    py test_endpoints.py
"""

import requests
import json


BASE_URL = "http://127.0.0.1:5000"


def print_result(name, response):
    """Helper function for clean test output."""
    print(f"\n🔹 {name}")
    try:
        data = response.json()
    except Exception:
        data = response.text
    print(f"Status: {response.status_code}")
    print("Response:", json.dumps(data, indent=2))


def test_root():
    """Test root route (/)"""
    r = requests.get(f"{BASE_URL}/")
    print_result("Root Route", r)


def test_create_user():
    """Test POST /api/users/"""
    payload = {"name": "Micah Porter", "email": "micah@example.com"}
    r = requests.post(f"{BASE_URL}/api/users/", json=payload)
    print_result("Create User", r)


def test_get_users():
    """Test GET /api/users/"""
    r = requests.get(f"{BASE_URL}/api/users/")
    print_result("Get Users", r)


def test_create_event():
    """Test POST /api/events/"""
    payload = {
        "title": "Hackathon",
        "date": "2025-11-12",
        "location": "NSU Auditorium",
        "description": "Coding event",
        "user_id": 1
    }
    r = requests.post(f"{BASE_URL}/api/events/", json=payload)
    print_result("Create Event", r)


def test_get_events():
    """Test GET /api/events/"""
    r = requests.get(f"{BASE_URL}/api/events/")
    print_result("Get Events", r)


def test_ai_status():
    """Test GET /api/ai/status"""
    r = requests.get(f"{BASE_URL}/api/ai/status")
    print_result("AI Status", r)


def test_ai_suggestions():
    """Test POST /api/ai/suggestions"""
    payload = {"preferences": ["on-campus", "low budget", "social"]}
    r = requests.post(f"{BASE_URL}/api/ai/suggestions", json=payload)
    print_result("AI Suggestions", r)


if __name__ == "__main__":
    print("\n=== 🔍 Testing Event Planner API ===")

    try:
        test_root()
        test_create_user()
        test_get_users()
        test_create_event()
        test_get_events()
        test_ai_status()
        test_ai_suggestions()
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to the Flask app. Make sure it’s running with:")
        print("   py app.py")
    else:
        print("\n✅ All tests completed successfully.")

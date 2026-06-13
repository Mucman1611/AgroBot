import pytest
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app
from database import Base, engine, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = "sqlite:///./test_agriassistant.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

client = TestClient(app)

def register_and_login(email, password, role, name="Test User"):
    client.post("/api/register", json={"full_name": name, "email": email, "password": password, "role": role})
    res = client.post("/api/login", json={"email": email, "password": password})
    return res.json()["token"]

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_register_farmer(self):
        res = client.post("/api/register", json={
            "full_name": "Franjo Horvat",
            "email": "franjo@opg.hr",
            "password": "lozinka123",
            "role": "farmer"
        })
        assert res.status_code == 200
        assert "id" in res.json()

    def test_register_duplicate_email(self):
        client.post("/api/register", json={"full_name": "A", "email": "a@a.hr", "password": "pass", "role": "farmer"})
        res = client.post("/api/register", json={"full_name": "B", "email": "a@a.hr", "password": "pass", "role": "farmer"})
        assert res.status_code == 400

    def test_login_success(self):
        client.post("/api/register", json={"full_name": "Test", "email": "t@t.hr", "password": "pass123", "role": "farmer"})
        res = client.post("/api/login", json={"email": "t@t.hr", "password": "pass123"})
        assert res.status_code == 200
        data = res.json()
        assert "token" in data
        assert data["role"] == "farmer"

    def test_login_wrong_password(self):
        client.post("/api/register", json={"full_name": "Test", "email": "x@x.hr", "password": "pravi", "role": "farmer"})
        res = client.post("/api/login", json={"email": "x@x.hr", "password": "krivi"})
        assert res.status_code == 401

    def test_login_nonexistent_user(self):
        res = client.post("/api/login", json={"email": "nitko@nema.hr", "password": "pass"})
        assert res.status_code == 401

    def test_protected_route_without_token(self):
        res = client.get("/api/farmer/farms")
        assert res.status_code == 401

    def test_register_agent(self):
        res = client.post("/api/register", json={"full_name": "Zdenka", "email": "z@z.hr", "password": "pass", "role": "agent"})
        assert res.status_code == 200

    def test_get_user_by_email(self):
        client.post("/api/register", json={"full_name": "Traženi", "email": "trazi@me.hr", "password": "p", "role": "farmer"})
        res = client.get("/api/user/by-email?email=trazi@me.hr")
        assert res.status_code == 200
        assert "id" in res.json()


class TestFarmer:
    def test_farmer_gets_empty_farms(self):
        token = register_and_login("farmer1@test.hr", "pass", "farmer")
        res = client.get("/api/farmer/farms", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json() == []

    def test_farmer_add_farm(self):
        token = register_and_login("farmer2@test.hr", "pass", "farmer")
        res = client.post("/api/farmer/farms/add", json={
            "name": "OPG Testni",
            "location": "Zagreb",
            "total_area_ha": 5.5
        }, headers=auth_headers(token))
        assert res.status_code == 200
        assert "id" in res.json()

    def test_farmer_sees_own_farms(self):
        token = register_and_login("farmer3@test.hr", "pass", "farmer")
        client.post("/api/farmer/farms/add", json={"name": "Moj OPG", "location": "Split", "total_area_ha": 3.0}, headers=auth_headers(token))
        res = client.get("/api/farmer/farms", headers=auth_headers(token))
        assert res.status_code == 200
        farms = res.json()
        assert len(farms) == 1
        assert farms[0]["name"] == "Moj OPG"

    def test_farmer_cannot_see_other_farmers_farms(self):
        token1 = register_and_login("f1@test.hr", "pass", "farmer")
        token2 = register_and_login("f2@test.hr", "pass", "farmer")
        client.post("/api/farmer/farms/add", json={"name": "Tuđi OPG", "location": "Osijek", "total_area_ha": 10.0}, headers=auth_headers(token1))
        res = client.get("/api/farmer/farms", headers=auth_headers(token2))
        assert res.json() == []

    def test_voice_command_returns_success(self):
        token = register_and_login("voice@test.hr", "pass", "farmer")
        res = client.post("/api/voice/command", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json()["status"] == "success"


class TestAgent:
    def test_agent_gets_empty_farms(self):
        token = register_and_login("agent1@test.hr", "pass", "agent")
        res = client.get("/api/agent/farms", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json() == []

    def test_farmer_cannot_access_agent_endpoint(self):
        token = register_and_login("farmer_bad@test.hr", "pass", "farmer")
        res = client.get("/api/agent/farms", headers=auth_headers(token))
        assert res.status_code == 403

    def test_agent_add_farm(self):
        token = register_and_login("agent2@test.hr", "pass", "agent")
        res = client.post("/api/agent/farms/add", json={
            "name": "OPG Klijenta",
            "location": "Rijeka",
            "total_area_ha": 8.0,
            "owner_email": "klijent@opg.hr"
        }, headers=auth_headers(token))
        assert res.status_code == 200

    def test_agent_sees_own_farms(self):
        token = register_and_login("agent3@test.hr", "pass", "agent")
        client.post("/api/agent/farms/add", json={"name": "OPG A", "location": "Varaždin", "total_area_ha": 12.0, "owner_email": "vlasnik@opg.hr"}, headers=auth_headers(token))
        res = client.get("/api/agent/farms", headers=auth_headers(token))
        farms = res.json()
        assert len(farms) == 1
        assert "deadlines" in farms[0]
        assert "applications" in farms[0]

    def test_agent_calendar_empty(self):
        token = register_and_login("agent4@test.hr", "pass", "agent")
        res = client.get("/api/agent/calendar?month=0", headers=auth_headers(token))
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_agent_submit_application(self):
        token = register_and_login("agent5@test.hr", "pass", "agent")
        client.post("/api/agent/farms/add", json={"name": "OPG Submit", "location": "Pula", "total_area_ha": 5.0, "owner_email": "sub@opg.hr"}, headers=auth_headers(token))
        farms = client.get("/api/agent/farms", headers=auth_headers(token)).json()
        farm_id = farms[0]["id"]
        seed_res = client.post("/api/seed")
        competitions = client.get("/api/competitions/available", headers=auth_headers(token)).json()
        if competitions:
            res = client.post(f"/api/agent/farm/{farm_id}/submit", json={
                "competition_id": competitions[0]["id"],
                "notes": "Test prijava"
            }, headers=auth_headers(token))
            assert res.status_code == 200

    def test_agent_cannot_submit_for_other_agents_farm(self):
        token1 = register_and_login("agentX@test.hr", "pass", "agent")
        token2 = register_and_login("agentY@test.hr", "pass", "agent")
        client.post("/api/agent/farms/add", json={"name": "Tuđi OPG", "location": "Zadar", "total_area_ha": 6.0, "owner_email": "tko@opg.hr"}, headers=auth_headers(token1))
        farms = client.get("/api/agent/farms", headers=auth_headers(token1)).json()
        farm_id = farms[0]["id"]
        client.post("/api/seed")
        competitions = client.get("/api/competitions/available", headers=auth_headers(token2)).json()
        if competitions:
            res = client.post(f"/api/agent/farm/{farm_id}/submit", json={"competition_id": competitions[0]["id"]}, headers=auth_headers(token2))
            assert res.status_code == 404


class TestCompetitions:
    def test_competitions_available(self):
        client.post("/api/seed")
        token = register_and_login("comp@test.hr", "pass", "farmer")
        res = client.get("/api/competitions/available", headers=auth_headers(token))
        assert res.status_code == 200
        competitions = res.json()
        assert len(competitions) > 0
        assert "name" in competitions[0]
        assert "deadline" in competitions[0]

    def test_seed_idempotent(self):
        client.post("/api/seed")
        client.post("/api/seed")
        token = register_and_login("seed2@test.hr", "pass", "farmer")
        res = client.get("/api/competitions/available", headers=auth_headers(token))
        assert len(res.json()) == 4
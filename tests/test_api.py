"""
RouteZone -- Tests API unifiee
===============================
Lancer : pytest tests/test_api.py -v
Utilise FastAPI TestClient.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "api"))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

API_KEY = "routezone-secret-2024"
HEADERS = {"X-API-Key": API_KEY}

ACCIDENT_VALIDE = {
    "lum": 1, "agg": 2, "int_": 1, "atm": 1, "col": 3, "catr": 3,
    "circ": 2, "vosp": 0, "prof": 1, "plan": 1, "surf": 1, "infra": 0,
    "situ": 1, "vma": 80, "catu": 1, "sexe": 1, "trajet": 5, "secu1": 1,
    "catv": 7, "age": 35, "heure": 14, "mois": 6, "jour": 15,
    "temperature": 18.5, "precipitation": 0.0, "windspeed": 12.0,
}


# ── Health check ─────────────────────────────────────────────────

def test_accueil_public():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "routes" in data


# ── Auth ─────────────────────────────────────────────────────────

def test_auth_sans_cle_retourne_403():
    r = client.get("/accidents/stats")
    assert r.status_code == 403

def test_auth_cle_invalide_retourne_403():
    r = client.get("/accidents/stats", headers={"X-API-Key": "mauvaise"})
    assert r.status_code == 403

def test_auth_cle_valide_retourne_200():
    r = client.get("/accidents/stats", headers=HEADERS)
    assert r.status_code == 200


# ── Routes donnees ───────────────────────────────────────────────

def test_stats_structure():
    r = client.get("/accidents/stats", headers=HEADERS)
    data = r.json()
    assert "total_accidents" in data
    assert "par_annee" in data
    assert "par_gravite" in data
    assert data["total_accidents"] > 0

def test_accidents_liste():
    r = client.get("/accidents?limite=5", headers=HEADERS)
    data = r.json()
    assert "accidents" in data
    assert data["total"] <= 5

def test_accidents_filtre_departement():
    r = client.get("/accidents?departement=69&limite=5", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["filtres"]["departement"] == "69"

def test_departement_69():
    r = client.get("/accidents/departement/69", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["total_accidents"] > 0

def test_departement_inexistant():
    r = client.get("/accidents/departement/99", headers=HEADERS)
    assert r.status_code == 404

def test_gravite_repartition():
    r = client.get("/accidents/gravite", headers=HEADERS)
    data = r.json()
    assert "repartition" in data
    total_pct = sum(item["pourcentage"] for item in data["repartition"])
    assert abs(total_pct - 100.0) < 1.0

def test_meteo_stats():
    r = client.get("/meteo/stats", headers=HEADERS)
    assert r.status_code == 200

def test_onisr_barometre():
    r = client.get("/onisr/barometre", headers=HEADERS)
    assert r.status_code == 200


# ── Routes IA ────────────────────────────────────────────────────

def test_predict_sans_cle():
    r = client.post("/predict", json=ACCIDENT_VALIDE)
    assert r.status_code == 403

def test_predict_valide():
    r = client.post("/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["prediction"] in [0, 1]
    assert data["label"] in ["Pas grave", "Grave"]
    assert 0.0 <= data["probability"] <= 100.0
    assert "model_version" in data

def test_predict_coherence():
    r = client.post("/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    data = r.json()
    if data["prediction"] == 1:
        assert data["label"] == "Grave"
    else:
        assert data["label"] == "Pas grave"

def test_predict_champ_manquant():
    incomplet = ACCIDENT_VALIDE.copy()
    del incomplet["age"]
    r = client.post("/predict", json=incomplet, headers=HEADERS)
    assert r.status_code == 422

def test_predict_body_vide():
    r = client.post("/predict", json={}, headers=HEADERS)
    assert r.status_code == 422

def test_predict_type_invalide():
    invalide = ACCIDENT_VALIDE.copy()
    invalide["age"] = "trente-cinq"
    r = client.post("/predict", json=invalide, headers=HEADERS)
    assert r.status_code == 422


# ── Auth JWT ─────────────────────────────────────────────────────

def test_auth_register_login_me():
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"

    # Register
    r = client.post("/auth/register", json={"email": email, "password": "secret123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]

    # Me
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email

    # Login
    r = client.post("/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.json()

    # Mauvais password
    r = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 401

    # Doublon register
    r = client.post("/auth/register", json={"email": email, "password": "secret123"})
    assert r.status_code == 409

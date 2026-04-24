"""
RouteZone — Tests API IA
========================
Tests automatisés sur les endpoints de l'API IA (port 8001).
Lancer avec : pytest tests/test_api_ia.py -v

Prérequis : l'API IA doit tourner sur http://localhost:8001
    cd src/api_ia && uvicorn main:app --reload --port 8001
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001"
API_KEY  = "routezone-secret-2024"
HEADERS  = {"X-API-Key": API_KEY}

# Données d'un accident type pour les tests
ACCIDENT_VALIDE = {
    "lum": 1,
    "agg": 2,
    "int_": 1,
    "atm": 1,
    "col": 3,
    "catr": 3,
    "circ": 2,
    "vosp": 0,
    "prof": 1,
    "plan": 1,
    "surf": 1,
    "infra": 0,
    "situ": 1,
    "vma": 80,
    "catu": 1,
    "sexe": 1,
    "trajet": 5,
    "secu1": 1,
    "catv": 7,
    "age": 35,
    "heure": 14,
    "mois": 6,
    "temperature": 18.5,
    "precipitation": 0.0,
    "windspeed": 12.0
}


# ── Route publique ────────────────────────────────────────────────

def test_accueil_public():
    """La route / est publique et retourne 200 sans clé."""
    r = httpx.get(f"{BASE_URL}/")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert data["status"] == "ok"


# ── Authentification ──────────────────────────────────────────────

def test_predict_sans_cle_retourne_403():
    """Un appel à /predict sans clé API doit retourner 403."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE)
    assert r.status_code == 403

def test_predict_cle_invalide_retourne_403():
    """Une clé API incorrecte doit retourner 403."""
    r = httpx.post(
        f"{BASE_URL}/predict",
        json=ACCIDENT_VALIDE,
        headers={"X-API-Key": "mauvaise-cle"}
    )
    assert r.status_code == 403

def test_predict_avec_cle_retourne_200():
    """Un appel valide à /predict doit retourner 200."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    assert r.status_code == 200


# ── Structure de la réponse /predict ─────────────────────────────

def test_predict_structure_json():
    """La réponse de /predict contient les bonnes clés."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    data = r.json()
    assert "prediction" in data
    assert "label" in data
    assert "probability" in data

def test_predict_prediction_binaire():
    """La prédiction doit être 0 ou 1."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    data = r.json()
    assert data["prediction"] in [0, 1]

def test_predict_label_valide():
    """Le label doit être 'Pas grave' ou 'Grave'."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    data = r.json()
    assert data["label"] in ["Pas grave", "Grave"]

def test_predict_probability_entre_0_et_100():
    """La probabilité doit être entre 0 et 100."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    data = r.json()
    assert 0.0 <= data["probability"] <= 100.0

def test_predict_coherence_prediction_label():
    """Si prediction = 1 alors label = 'Grave', si 0 alors 'Pas grave'."""
    r = httpx.post(f"{BASE_URL}/predict", json=ACCIDENT_VALIDE, headers=HEADERS)
    data = r.json()
    if data["prediction"] == 1:
        assert data["label"] == "Grave"
    else:
        assert data["label"] == "Pas grave"


# ── Validation des données d'entrée ──────────────────────────────

def test_predict_age_texte_retourne_422():
    """Envoyer un texte pour un champ entier doit retourner 422."""
    accident_invalide = ACCIDENT_VALIDE.copy()
    accident_invalide["age"] = "trente-cinq"
    r = httpx.post(f"{BASE_URL}/predict", json=accident_invalide, headers=HEADERS)
    assert r.status_code == 422

def test_predict_champ_manquant_retourne_422():
    """Un champ manquant dans le body doit retourner 422."""
    accident_incomplet = ACCIDENT_VALIDE.copy()
    del accident_incomplet["age"]
    r = httpx.post(f"{BASE_URL}/predict", json=accident_incomplet, headers=HEADERS)
    assert r.status_code == 422

def test_predict_body_vide_retourne_422():
    """Un body vide doit retourner 422."""
    r = httpx.post(f"{BASE_URL}/predict", json={}, headers=HEADERS)
    assert r.status_code == 422


# ── Cohérence métier ──────────────────────────────────────────────

def test_predict_accident_nuit_haute_vitesse():
    """Un accident de nuit à haute vitesse doit avoir une probabilité GRAVE non nulle."""
    accident_grave = ACCIDENT_VALIDE.copy()
    accident_grave["lum"] = 5      # nuit sans éclairage
    accident_grave["vma"] = 130    # autoroute
    accident_grave["age"] = 22     # jeune conducteur
    r = httpx.post(f"{BASE_URL}/predict", json=accident_grave, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["probability"] > 0

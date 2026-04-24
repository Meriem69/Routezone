"""
RouteZone — Tests API données
=============================
Tests automatisés sur les 7 endpoints de l'API données (port 8000).
Lancer avec : pytest tests/test_api_data.py -v

Prérequis : l'API données doit tourner sur http://localhost:8000
    cd src/api_data && uvicorn main:app --reload
"""

import pytest
import httpx

BASE_URL = "http://localhost:8000"
API_KEY  = "routezone-secret-2024"
HEADERS  = {"X-API-Key": API_KEY}


# ── Route publique ────────────────────────────────────────────────

def test_accueil_public():
    """La route / est publique et retourne 200 sans clé."""
    r = httpx.get(f"{BASE_URL}/")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert "endpoints" in data


# ── Authentification ──────────────────────────────────────────────

def test_accidents_sans_cle_retourne_403():
    """Un appel sans clé API doit retourner 403."""
    r = httpx.get(f"{BASE_URL}/accidents/stats")
    assert r.status_code == 403

def test_accidents_cle_invalide_retourne_403():
    """Une clé API incorrecte doit retourner 403."""
    r = httpx.get(f"{BASE_URL}/accidents/stats", headers={"X-API-Key": "mauvaise-cle"})
    assert r.status_code == 403

def test_accidents_avec_cle_retourne_200():
    """Un appel avec la bonne clé doit retourner 200."""
    r = httpx.get(f"{BASE_URL}/accidents/stats", headers=HEADERS)
    assert r.status_code == 200


# ── Endpoint /accidents/stats ─────────────────────────────────────

def test_stats_structure_json():
    """L'endpoint /accidents/stats retourne les bonnes clés JSON."""
    r = httpx.get(f"{BASE_URL}/accidents/stats", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "total_accidents" in data
    assert "par_annee" in data
    assert "par_gravite" in data
    assert "top_10_departements" in data

def test_stats_total_positif():
    """Le total d'accidents doit être un entier positif."""
    r = httpx.get(f"{BASE_URL}/accidents/stats", headers=HEADERS)
    data = r.json()
    assert isinstance(data["total_accidents"], int)
    assert data["total_accidents"] > 0


# ── Endpoint /accidents ───────────────────────────────────────────

def test_accidents_retourne_liste():
    """L'endpoint /accidents retourne une liste d'accidents."""
    r = httpx.get(f"{BASE_URL}/accidents", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "accidents" in data
    assert "total" in data
    assert isinstance(data["accidents"], list)

def test_accidents_limite_par_defaut():
    """Sans paramètre limite, le résultat ne dépasse pas 100."""
    r = httpx.get(f"{BASE_URL}/accidents", headers=HEADERS)
    data = r.json()
    assert data["total"] <= 100

def test_accidents_filtre_departement():
    """Le filtre département retourne uniquement les accidents du département."""
    r = httpx.get(f"{BASE_URL}/accidents?departement=69&limite=10", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["filtres"]["departement"] == "69"

def test_accidents_filtre_annee():
    """Le filtre année retourne uniquement les accidents de l'année demandée."""
    r = httpx.get(f"{BASE_URL}/accidents?annee=2022&limite=10", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["filtres"]["annee"] == 2022


# ── Endpoint /accidents/departement/{dep} ────────────────────────

def test_departement_69_retourne_200():
    """Le département 69 existe dans la base et retourne 200."""
    r = httpx.get(f"{BASE_URL}/accidents/departement/69", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["departement"] == "69"
    assert data["total_accidents"] > 0

def test_departement_inexistant_retourne_404():
    """Un département inexistant doit retourner 404."""
    r = httpx.get(f"{BASE_URL}/accidents/departement/99", headers=HEADERS)
    assert r.status_code == 404


# ── Endpoint /accidents/gravite ───────────────────────────────────

def test_gravite_retourne_repartition():
    """L'endpoint gravité retourne une répartition avec pourcentages."""
    r = httpx.get(f"{BASE_URL}/accidents/gravite", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "repartition" in data
    assert "total_usagers" in data
    assert len(data["repartition"]) > 0

def test_gravite_pourcentages_somme_100():
    """La somme des pourcentages de gravité doit être proche de 100%."""
    r = httpx.get(f"{BASE_URL}/accidents/gravite", headers=HEADERS)
    data = r.json()
    total_pct = sum(item["pourcentage"] for item in data["repartition"])
    assert abs(total_pct - 100.0) < 1.0


# ── Endpoint /meteo/stats ─────────────────────────────────────────

def test_meteo_stats_retourne_200():
    """L'endpoint météo retourne 200 avec la clé."""
    r = httpx.get(f"{BASE_URL}/meteo/stats", headers=HEADERS)
    assert r.status_code == 200


# ── Endpoint /onisr/barometre ─────────────────────────────────────

def test_onisr_barometre_retourne_200():
    """L'endpoint ONISR retourne 200 avec la clé."""
    r = httpx.get(f"{BASE_URL}/onisr/barometre", headers=HEADERS)
    assert r.status_code == 200

def test_onisr_filtre_annee():
    """Le filtre année sur le baromètre ONISR fonctionne."""
    r = httpx.get(f"{BASE_URL}/onisr/barometre?annee=2022", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["annee_filtre"] == 2022

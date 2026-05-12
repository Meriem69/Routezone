"""
RouteZone -- Tests de coherence metier du modele ML
====================================================
Verifie que la probabilite predite varie dans le sens metier attendu
quand on change une variable a la fois.

Tolerance : on attend au moins +0.02 (point de pourcentage) de proba
plus grave pour le cas B vs A. Marge volontairement faible pour ne pas
faire echouer sur du bruit, tout en captant les vraies tendances.

Lancer : pytest tests/test_business_logic.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "api"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

API_KEY = "routezone-secret-2024"
HEADERS = {"X-API-Key": API_KEY}

BASE_PAYLOAD = {
    "lum": 1, "agg": 2, "int_": 1, "atm": 1, "col": 2, "catr": 4, "circ": 2,
    "vosp": 0, "prof": 1, "plan": 1, "surf": 1, "infra": 0, "situ": 1,
    "vma": 50, "catu": 1, "sexe": 1, "trajet": 1, "secu1": 1, "catv": 7,
    "age": 35, "heure": 14, "mois": 6, "jour": 15,
    "temperature": 15.0, "precipitation": 0.0, "windspeed": 10.0,
    "lat": 45.7578, "lon": 4.8320,
}

TOLERANCE = 0.02  # marge minimale entre proba B et proba A


def _proba(overrides: dict) -> float:
    """Envoie BASE_PAYLOAD avec overrides ecrases et renvoie la proba."""
    payload = {**BASE_PAYLOAD, **overrides}
    r = client.post("/predict", json=payload, headers=HEADERS)
    assert r.status_code == 200, f"API renvoie {r.status_code} : {r.text[:200]}"
    return float(r.json()["probability"])


# ── Coherence metier ────────────────────────────────────────────

def test_frontale_plus_grave_que_arriere():
    """col=1 (frontale) doit donner une proba >= col=2 (par arriere)."""
    proba_a = _proba({"col": 2})  # par arriere
    proba_b = _proba({"col": 1})  # frontale
    assert proba_b > proba_a + TOLERANCE, (
        f"Frontale ({proba_b}) attendue plus grave qu'arriere ({proba_a})"
    )


def test_aucun_equipement_plus_grave_que_ceinture():
    """secu1=0 (aucun equipement) doit etre plus grave que secu1=1 (ceinture)."""
    proba_a = _proba({"secu1": 1})  # ceinture
    proba_b = _proba({"secu1": 0})  # aucun
    assert proba_b > proba_a + TOLERANCE, (
        f"Aucun equipement ({proba_b}) attendu plus grave que ceinture ({proba_a})"
    )


def test_nuit_plus_grave_que_jour():
    """lum=3 (nuit sans eclairage) plus grave que lum=1 (plein jour)
    dans un contexte deja risque (moto sans equipement)."""
    risky_context = {"catv": 33, "secu1": 0}  # moto + aucun equipement
    proba_a = _proba({**risky_context, "lum": 1})  # plein jour
    proba_b = _proba({**risky_context, "lum": 3})  # nuit sans eclairage
    assert proba_b > proba_a + TOLERANCE, (
        f"Nuit ({proba_b}) attendue plus grave que jour ({proba_a}) "
        f"dans un contexte moto sans equipement"
    )


def test_moto_plus_grave_que_voiture():
    """catv=33 (moto >125cc) plus grave que catv=7 (voiture)."""
    proba_a = _proba({"catv": 7})    # voiture
    proba_b = _proba({"catv": 33})   # moto
    assert proba_b > proba_a + TOLERANCE, (
        f"Moto ({proba_b}) attendue plus grave que voiture ({proba_a})"
    )


def test_vma_haute_plus_grave_que_vma_basse():
    """vma=130 (autoroute) plus grave que vma=50 (ville)."""
    proba_a = _proba({"vma": 50})
    proba_b = _proba({"vma": 130})
    assert proba_b > proba_a + TOLERANCE, (
        f"VMA 130 ({proba_b}) attendue plus grave que VMA 50 ({proba_a})"
    )

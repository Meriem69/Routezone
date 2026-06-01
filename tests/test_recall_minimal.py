"""
RouteZone -- Test de non-regression sur cas metier extremes
============================================================
Garantit que le modele servi par l'API classifie correctement des cas
extremes ou la gravite est certaine d'un point de vue metier.

Ce test a ete ajoute suite a l'incident calibrator (mai 2026) :
le CalibratedClassifierCV isotonique avait silencieusement degrade
le Recall sur la classe GRAVE (76% -> 33%). Aucun test existant ne
detectait cette regression car les tests de coherence verifiaient
des tendances relatives (cas B > cas A) et non des seuils absolus.

Strategie : on definit 10 scenarios "metier evidents" (moto sans
equipement la nuit sur autoroute enneigee, etc.) et on exige qu'au
moins 8/10 soient predits GRAVE avec une probabilite >= 0.60.

Lancer : pytest tests/test_recall_minimal.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "api"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

API_KEY = "routezone-secret-2024"
HEADERS = {"X-API-Key": API_KEY}

# Payload de base : un cas neutre que l'on modifiera scenario par scenario.
# On reprend exactement la meme structure que test_business_logic.py
# pour rester coherent avec l'existant.
BASE_PAYLOAD = {
    "lum": 1, "agg": 2, "int_": 1, "atm": 1, "col": 2, "catr": 4, "circ": 2,
    "vosp": 0, "prof": 1, "plan": 1, "surf": 1, "infra": 0, "situ": 1,
    "vma": 50, "catu": 1, "sexe": 1, "trajet": 1, "secu1": 1, "catv": 7,
    "age": 35, "heure": 14, "mois": 6, "jour": 15,
    "temperature": 15.0, "precipitation": 0.0, "windspeed": 10.0,
    "lat": 45.7578, "lon": 4.8320,
}

# Seuil minimal de probabilite GRAVE pour qu'un cas extreme soit "valide".
# Choisi a 0.60 : assez exigeant pour detecter une regression majeure
# (cas calibrator 33%) mais pas au point de capter le bruit normal.
PROBA_MIN = 60.0

# Tolerance metier : on accepte 2 echecs sur 10 cas extremes.
# Un seul cas mal classifie ne disqualifie pas le modele ; en revanche
# 3+ echecs signalent une regression systemique.
MIN_CAS_CORRECTS = 8


def _predire(overrides: dict) -> dict:
    """
    Envoie BASE_PAYLOAD enrichi des overrides a l'API et renvoie le JSON.
    Equivalent du helper _proba() de test_business_logic, mais retourne
    le dict complet (label + probability) au lieu de juste la proba.
    """
    payload = {**BASE_PAYLOAD, **overrides}
    r = client.post("/predict", json=payload, headers=HEADERS)
    assert r.status_code == 200, f"API renvoie {r.status_code} : {r.text[:200]}"
    return r.json()

# ============================================================
# LES 10 CAS METIER OU LA GRAVITE EST EVIDENTE
# ============================================================
# Chq scenario combine plusieurs facteurs aggravants ou un facteur
# aggravant extreme. Un modele correct doit pouvoir predire GRAVE avec une
# probabilite >= PROBA_MIN sur AU MOINS 8 de ces 10 cas.

CAS_EXTREMES = [
    {
        "nom": "Moto autoroute neige verglas nuit sans casque",
        "overrides": {
            "catv": 33,        # moto > 125cc
            "secu1": 0,        # aucun equipement
            "catr": 1,         # autoroute
            "vma": 130,        # vitesse max
            "atm": 7,          # neige
            "surf": 5,         # verglas
            "lum": 5,          # nuit sans eclairage
            "temperature": -5.0,
            "precipitation": 8.0,
        },
    },
    {
        "nom": "Frontale autoroute 130 conducteur age sans ceinture",
        "overrides": {
            "col": 1,          # frontale
            "catr": 1,         # autoroute
            "vma": 130,
            "secu1": 0,        # aucun equipement
            "age": 78,
            "catv": 7,
        },
    },
    {
        "nom": "Pieton hors agglomeration nuit pluie",
        "overrides": {
            "catu": 3,         # pieton
            "catv": 0,         # pas de vehicule
            "agg": 1,          # hors agglo
            "lum": 5,          # nuit sans eclairage
            "atm": 2,          # pluie legere
            "vma": 90,         # route departementale
            "secu1": 0,
        },
    },
    {
        "nom": "Velo route 90 nuit pluie sans casque",
        "overrides": {
            "catv": 1,         # bicyclette
            "secu1": 0,        # aucun equipement
            "vma": 90,
            "lum": 5,          # nuit sans eclairage
            "atm": 2,          # pluie
            "agg": 1,          # hors agglo
            "age": 45,
        },
    },
    {
        "nom": "Conducteur 18 ans moto nuit pluie verglas",
        "overrides": {
            "catv": 33,        # moto
            "secu1": 0,
            "age": 18,
            "lum": 5,
            "atm": 2,          # pluie
            "surf": 5,         # verglas
            "vma": 90,
        },
    },
    {
        "nom": "Frontale autoroute brouillard sans ceinture passager age",
        "overrides": {
            "col": 1,          # frontale
            "catr": 1,         # autoroute
            "vma": 130,
            "atm": 5,          # brouillard
            "secu1": 0,        # aucun equipement
            "catu": 2,         # passager
            "age": 72,         # age eleve
        },
    },
    {
        "nom": "Pieton age 82 hors agglo nuit pluie vma 90",
        "overrides": {
            "catu": 3,         # pieton
            "catv": 0,
            "age": 82,
            "agg": 1,          # hors agglo
            "lum": 5,          # nuit sans eclairage
            "atm": 2,          # pluie
            "vma": 90,         # vitesse elevee
        },
    },
    {
        "nom": "Moto 110 cm3 nuit autoroute pluie verglas sans casque",
        "overrides": {
            "catv": 32,        # moto 50-125cc
            "secu1": 0,        # aucun equipement
            "catr": 1,         # autoroute
            "vma": 130,
            "lum": 5,          # nuit sans eclairage
            "atm": 2,          # pluie
            "surf": 5,         # verglas
            "age": 19,         # jeune conducteur
        },
    },
    {
        "nom": "Frontale jeune conducteur sans ceinture campagne nuit",
        "overrides": {
            "col": 1,          # frontale
            "secu1": 0,
            "age": 19,
            "agg": 1,          # hors agglo
            "lum": 5,
            "vma": 90,
        },
    },
    {
        "nom": "Pieton enfant hors agglo nuit pluie vma 90",
        "overrides": {
            "catu": 3,         # pieton
            "catv": 0,
            "age": 8,
            "agg": 1,          # hors agglo
            "lum": 5,          # nuit sans eclairage
            "atm": 2,          # pluie
            "vma": 90,         # route departementale
        },
    },
]

# ============================================================
# TEST PRINCIPAL
# ============================================================

def test_recall_metier_cas_extremes():
    """
    Verifie que le modele servi atteint un Recall metier acceptable
    sur les 10 cas extremes definis ci-dessus.

    Un cas est considere "correctement classifie" si :
      - le label predit est "GRAVE"
      - ET la probability est >= PROBA_MIN (0.60)

    Le test passe si au moins MIN_CAS_CORRECTS (8) cas sur 10 sont
    correctement classifies.

    En cas d'echec, on affiche la liste detaillee des cas mal predits
    pour faciliter le diagnostic (typiquement en cas de regression
    type calibrator mai 2026).
    """
    resultats = []
    nb_corrects = 0

    for cas in CAS_EXTREMES:
        prediction = _predire(cas["overrides"])
        label = prediction.get("label", "INCONNU")
        proba = float(prediction.get("probability", 0.0))

        # Un cas est "correct" si label = GRAVE ET proba >= seuil
        est_correct = (label == "Grave") and (proba >= PROBA_MIN)
        if est_correct:
            nb_corrects += 1

        resultats.append({
            "nom": cas["nom"],
            "label": label,
            "proba": proba,
            "correct": est_correct,
        })

    # Affichage detaille pour faciliter le debug si echec
    print(f"\n{'='*70}")
    print(f"RESULTATS TEST RECALL METIER ({nb_corrects}/{len(CAS_EXTREMES)})")
    print(f"{'='*70}")
    for r in resultats:
        statut = "OK  " if r["correct"] else "FAIL"
        print(f"  [{statut}] {r['proba']:5.1f}% {r['label']:10s} -- {r['nom']}")
    print(f"{'='*70}")

    # Assertion finale : au moins 8 cas sur 10 doivent etre corrects
    assert nb_corrects >= MIN_CAS_CORRECTS, (
        f"REGRESSION DETECTEE : seulement {nb_corrects}/{len(CAS_EXTREMES)} "
        f"cas extremes correctement classifies (minimum requis : {MIN_CAS_CORRECTS}). "
        f"Cela suggere une regression du modele similaire a l'incident "
        f"calibrator du 14 mai 2026. Verifier routes_ia.py et les fichiers "
        f"de modeles dans models/."
    )
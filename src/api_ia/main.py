from fastapi import FastAPI, HTTPException, Header
from pathlib import Path
import joblib
import numpy as np
from pydantic import BaseModel
import os

# ── Authentification API Key ──────────────────────────────────────
API_KEY = os.getenv("API_KEY", "routezone-secret-2024")

def verifier_api_key(x_api_key: str):
    """Vérifie que la clé API fournie est valide. Lève 403 sinon."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Clé API invalide ou manquante")

# ── Chargement des fichiers au démarrage ──────────────────────────
# MODELS_DIR peut être défini via variable d'environnement (Docker)
# ou calculé depuis le chemin du fichier (local)
MODELS_DIR = Path(os.getenv(
    "MODELS_DIR",
    str(Path(__file__).parent.parent.parent / "models")
))

model         = joblib.load(MODELS_DIR / "best_model.pkl")
features      = joblib.load(MODELS_DIR / "features.pkl")
class_mapping = joblib.load(MODELS_DIR / "class_mapping.pkl")

print(f"Modele charge : {len(features)} features")
print(f"MODELS_DIR    : {MODELS_DIR}")

# ── Application FastAPI ───────────────────────────────────────────
app = FastAPI(
    title="RouteZone API IA",
    description="""
API REST exposant le modele LightGBM de prediction de gravite d'accidents routiers.

**Authentification :** header X-API-Key requis sur /predict.

**Seuil de decision :** 0.5 (seuil standard — meilleur equilibre Recall/Precision).
Differents seuils ont ete testes (0.35 a 0.5) — voir notebook_04 section 12.3.
    """,
    version="1.0.0"
)

# ── Modele de donnees d'entree ────────────────────────────────────
class AccidentInput(BaseModel):
    lum: int
    agg: int
    int_: int
    atm: int
    col: int
    catr: int
    circ: int
    vosp: int
    prof: int
    plan: int
    surf: int
    infra: int
    situ: int
    vma: int
    catu: int
    sexe: int
    trajet: int
    secu1: int
    catv: int
    age: int
    heure: int
    mois: int
    temperature: float
    precipitation: float
    windspeed: float

# ── Route d'accueil — publique ────────────────────────────────────
@app.get("/")
def accueil():
    return {
        "message": "RouteZone API IA",
        "status": "ok",
        "documentation": "/docs"
    }

# ── Route de prediction — protegee ───────────────────────────────
@app.post("/predict")
def predict(data: AccidentInput, x_api_key: str = Header(None)):
    """
    Predit la gravite d'un accident routier.

    Retourne :
    - **prediction** : 0 (Pas grave) ou 1 (Grave)
    - **label** : 'Pas grave' ou 'Grave'
    - **probability** : probabilite d'etre GRAVE en pourcentage
    """
    verifier_api_key(x_api_key)

    valeurs = [
        data.lum, data.agg, data.int_, data.atm, data.col, data.catr,
        data.circ, data.vosp, data.prof, data.plan, data.surf, data.infra,
        data.situ, data.vma, data.catu, data.sexe, data.trajet, data.secu1,
        data.catv, data.age, data.heure, data.mois,
        data.temperature, data.precipitation, data.windspeed
    ]

    X = np.array([valeurs])

    # Seuil 0.5 par defaut — meilleur equilibre Recall/Precision
    # Recall GRAVE : 0.796 | Precision GRAVE : 0.414 | F1 macro : 0.695
    pred_int    = int(model.predict(X)[0])
    probability = float(model.predict_proba(X)[0][1])

    if isinstance(class_mapping, dict):
        label = str(class_mapping[pred_int])
    else:
        val = class_mapping[pred_int]
        label = str(val.item() if hasattr(val, 'item') else val)

    return {
        "prediction": pred_int,
        "label": label,
        "probability": round(probability * 100, 1)
    }

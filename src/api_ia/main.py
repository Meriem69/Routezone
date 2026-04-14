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

# Chemins vers les modèles
MODELS_DIR = Path(__file__).parent.parent / "models"

# Chargement des 3 fichiers au démarrage de l'API
model         = joblib.load(MODELS_DIR / "best_model.pkl")
features      = joblib.load(MODELS_DIR / "features.pkl")
class_mapping = joblib.load(MODELS_DIR / "class_mapping.pkl")

print(f" ok Modèle chargé")
print(f" ok{len(features)} features : {features}")

app = FastAPI()

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

@app.get("/")
def accueil():
    return {"message": "RouteZone API IA", "status": "ok"}

@app.post("/predict")
def predict(data: AccidentInput, 
            x_api_key: str = Header(None)
):
    verifier_api_key(x_api_key)

    valeurs = [
        data.lum, data.agg, data.int_, data.atm, data.col, data.catr,
        data.circ, data.vosp, data.prof, data.plan, data.surf, data.infra,
        data.situ, data.vma, data.catu, data.sexe, data.trajet, data.secu1,
        data.catv, data.age, data.heure, data.mois,
        data.temperature, data.precipitation, data.windspeed
    ]

    X = np.array([valeurs])
    pred_raw = model.predict(X)
    pred_int = int(pred_raw[0])
    probability = float(model.predict_proba(X)[0][1])

    # class_mapping peut être un dict, une liste ou un array numpy
    if isinstance(class_mapping, dict):
        label = str(class_mapping[pred_int])
    else:
        # liste ou array numpy → indexation directe
        val = class_mapping[pred_int]
        label = str(val.item() if hasattr(val, 'item') else val)

    return {
        "prediction": pred_int,
        "label": label,
        "probability": round(probability * 100, 1)
    }
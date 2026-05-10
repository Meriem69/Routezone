"""
RouteZone -- Routes IA (/predict, /predictions)
Competences C8-C9 : Service IA + API IA
"""

from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
from typing import Optional
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from logger import logger

import joblib
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import text
import os

from db import engine
from security import verifier_api_key, verifier_api_key_ou_jwt, get_current_user, get_optional_user

router = APIRouter(tags=["Intelligence Artificielle"])

# ── Chargement du modele au demarrage (priorite V3 OSRM > V2 > V1) ────────
MODELS_DIR = Path(os.getenv(
    "MODELS_DIR",
    str(Path(__file__).parent.parent.parent / "models")
))

v3_path = MODELS_DIR / "best_model_v3_osrm.pkl"
v2_path = MODELS_DIR / "best_model_v2.pkl"

if v3_path.exists():
    model = joblib.load(v3_path)
    features = joblib.load(MODELS_DIR / "features_v3_osrm.pkl")
    cal_path = MODELS_DIR / "calibrator_v3_osrm.pkl"
    calibrator = joblib.load(cal_path) if cal_path.exists() else None
    MODEL_VERSION = "v3_osrm"
    print(f"Modele V3 OSRM charge : {len(features)} features (calibre: {calibrator is not None})")
elif v2_path.exists():
    model = joblib.load(v2_path)
    features = joblib.load(MODELS_DIR / "features_v2.pkl")
    cal_path = MODELS_DIR / "calibrator_v2.pkl"
    calibrator = joblib.load(cal_path) if cal_path.exists() else None
    MODEL_VERSION = "v2"
    print(f"Modele V2 charge : {len(features)} features (calibre: {calibrator is not None})")
else:
    model = joblib.load(MODELS_DIR / "best_model.pkl")
    features = joblib.load(MODELS_DIR / "features.pkl")
    calibrator = None
    MODEL_VERSION = "v1"
    print(f"Modele V1 charge : {len(features)} features")

class_mapping = joblib.load(MODELS_DIR / "class_mapping.pkl")


# ── Schema d'entree ──────────────────────────────────────────────
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
    vma: int = Field(..., ge=0, le=200)
    catu: int
    sexe: int
    trajet: int
    secu1: int
    catv: int
    age: int = Field(..., ge=0, le=120)
    heure: int = Field(..., ge=0, le=23)
    mois: int = Field(..., ge=1, le=12)
    temperature: float = Field(..., ge=-30, le=50)
    precipitation: float = Field(..., ge=0)
    windspeed: float = Field(..., ge=0, le=300)
    jour: int = 15
    lat: float = Field(None, ge=-90, le=90)
    lon: float = Field(None, ge=-180, le=180)
    # V3 OSRM : temps reels calcules cote Streamlit via OSRM Docker.
    # Optionnels : si fournis, on les utilise tels quels (route reelle).
    # Sinon fallback Haversine x 1.3 (compatibilite).
    nearest_pompiers_min: float = None
    nearest_sau_min: float = None


# ── Features derivees ────────────────────────────────────────────
def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def compute_derived_features(data: AccidentInput) -> dict:
    h = data.heure
    if 0 <= h <= 6: creneau = 0
    elif 7 <= h <= 9: creneau = 1
    elif 10 <= h <= 16: creneau = 2
    elif 17 <= h <= 21: creneau = 3
    else: creneau = 4

    if data.age < 25: age_tranche = 0
    elif data.age < 45: age_tranche = 1
    elif data.age < 65: age_tranche = 2
    else: age_tranche = 3

    try:
        jour_semaine = datetime(datetime.now().year, data.mois, data.jour).weekday()
    except ValueError:
        jour_semaine = 2

    # 1) Si Streamlit a deja calcule les temps OSRM reels, on les utilise.
    # 2) Sinon fallback Haversine x 1.3 sur centres_urgences.csv (V1/V2 legacy).
    if data.nearest_pompiers_min is not None and data.nearest_sau_min is not None:
        nearest_pompiers_min = data.nearest_pompiers_min
        nearest_sau_min = data.nearest_sau_min
    else:
        nearest_sau_min = 15.0
        nearest_pompiers_min = 10.0
        if data.lat is not None and data.lon is not None:
            centres_path = Path(__file__).parent.parent.parent / "data" / "processed" / "centres_urgences.csv"
            if centres_path.exists():
                try:
                    centres = pd.read_csv(centres_path)
                    for ctype in ("urgences_sau", "pompiers"):
                        sub = centres[centres["type"] == ctype]
                        if not sub.empty:
                            dists = sub.apply(
                                lambda r: _haversine(data.lat, data.lon, r["lat"], r["lon"]),
                                axis=1)
                            temps = round(dists.min() * 1.3 / 60 * 60, 1)
                            if ctype == "urgences_sau":
                                nearest_sau_min = temps
                            else:
                                nearest_pompiers_min = temps
                except Exception:
                    pass

    temps_total = round(nearest_pompiers_min + nearest_sau_min, 1)
    is_zone_blanche = int(temps_total > 30)

    derived = {
        "creneau": creneau,
        "age_tranche": age_tranche,
        "jour_semaine": jour_semaine,
        "is_weekend": int(jour_semaine >= 5),
        "vma_x_nuit": data.vma * int(data.lum >= 3),
        "jeune_2roues": int(data.age < 25 and data.catv in [2, 30, 31, 32]),
        "pluie_x_surface": int(data.atm in [2, 3] and data.surf in [2, 3, 4]),
    }
    # V3 OSRM
    if "temps_total_osrm" in features:
        derived["temps_total_osrm"] = temps_total
    if "zone_blanche_osrm" in features:
        derived["zone_blanche_osrm"] = is_zone_blanche
    # V2 Haversine (compat retro)
    if "temps_total_prise_en_charge" in features:
        derived["temps_total_prise_en_charge"] = temps_total
    if "zone_blanche" in features:
        derived["zone_blanche"] = is_zone_blanche
    return derived


# ── Prediction ───────────────────────────────────────────────────
@router.post("/predict")
def predict(
    data: AccidentInput,
    user: Optional[dict] = Depends(get_optional_user),
    _: str = Depends(verifier_api_key_ou_jwt),
):
    """Predit la gravite d'un accident. Sauvegarde dans l'historique si JWT fourni."""
    logger.info(f"Prediction demandee : age={data.age}, vma={data.vma}, heure={data.heure}")
    
    base = {
        "lum": data.lum, "agg": data.agg, "atm": data.atm,
        "col": data.col, "catr": data.catr, "circ": data.circ,
        "vosp": data.vosp, "prof": data.prof, "plan": data.plan,
        "surf": data.surf, "infra": data.infra, "situ": data.situ,
        "vma": data.vma, "catu": data.catu, "sexe": data.sexe,
        "trajet": data.trajet, "secu1": data.secu1, "catv": data.catv,
        "age": data.age, "heure": data.heure, "mois": data.mois,
        "temperature": data.temperature,
        "precipitation": data.precipitation,
        "windspeed": data.windspeed,
    }

    base["int_feat"] = data.int_

    if MODEL_VERSION in ("v2", "v3_osrm"):
        base.update(compute_derived_features(data))

    row = [base.get(f, 0) for f in features]
    X = pd.DataFrame([row], columns=features)

    # Convertir les catégorielles comme pendant le training
    CAT_FEATURES = [
        "lum", "agg", "atm", "col", "catr", "circ", "vosp", "prof", "plan",
        "surf", "infra", "situ", "catu", "sexe", "trajet", "secu1", "catv",
        "creneau", "age_tranche", "jour_semaine", "int_feat",
    ]
    for col in CAT_FEATURES:
        if col in X.columns:
            X[col] = X[col].astype(int).astype("category")

    proba = (calibrator or model).predict_proba(X)[0]
    probability = float(proba[1])
    pred_int = int(probability >= 0.5)

    if isinstance(class_mapping, dict):
        label = str(class_mapping[pred_int])
    else:
        val = class_mapping[pred_int]
        label = str(val.item() if hasattr(val, 'item') else val)

    prob_pct = round(probability * 100, 1)

    if user is not None:
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO predictions (user_id, lum, agg, atm, col, catr, vma, catu, sexe, age, heure, mois, jour, lat, lon, prediction, label, probability, model_version)
                    VALUES (:uid, :lum, :agg, :atm, :col, :catr, :vma, :catu, :sexe, :age, :heure, :mois, :jour, :lat, :lon, :pred, :label, :prob, :mv)
                """), {"uid": user["id"], "lum": data.lum, "agg": data.agg, "atm": data.atm,
                       "col": data.col, "catr": data.catr, "vma": data.vma, "catu": data.catu,
                       "sexe": data.sexe, "age": data.age, "heure": data.heure, "mois": data.mois,
                       "jour": data.jour, "lat": data.lat, "lon": data.lon,
                       "pred": pred_int, "label": label, "prob": prob_pct, "mv": MODEL_VERSION})
        except Exception:
            pass
    logger.info(f"Prediction terminee : resultat={pred_int}, label={label}, proba={prob_pct}%, model={MODEL_VERSION}")        
    return {"prediction": pred_int, "label": label, "probability": prob_pct, "model_version": MODEL_VERSION}


# ── Historique ───────────────────────────────────────────────────
@router.get("/predictions")
def list_predictions(limit: int = 50, user: dict = Depends(get_current_user)):
    """Historique des predictions de l'utilisateur connecte."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, created_at, lum, agg, atm, col, catr, vma, catu, sexe, age, heure, mois, jour, lat, lon, prediction, label, probability, model_version
            FROM predictions WHERE user_id = :uid ORDER BY created_at DESC LIMIT :lim
        """), {"uid": user["id"], "lim": limit}).fetchall()

    return {
        "user_id": user["id"], "total": len(rows),
        "predictions": [{
            "id": r[0], "date": r[1].isoformat() if r[1] else None,
            "inputs": {"lum": r[2], "agg": r[3], "atm": r[4], "col": r[5], "catr": r[6], "vma": r[7],
                       "catu": r[8], "sexe": r[9], "age": r[10], "heure": r[11], "mois": r[12], "jour": r[13],
                       "lat": r[14], "lon": r[15]},
            "prediction": r[16], "label": r[17], "probability": r[18], "model_version": r[19],
        } for r in rows]
    }

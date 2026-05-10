"""
RouteZone -- API unifiee
========================
FastAPI qui expose :
  - Routes donnees : /accidents, /meteo, /onisr (C5)
  - Routes IA : /predict, /predictions (C8-C9)
  - Routes auth : /auth/register, /auth/login (JWT)

Lancer :
    uvicorn main:app --reload --port 8001

Documentation : http://localhost:8001/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logger import logger
from routes_data import router as data_router
from routes_ia import router as ia_router
from routes_auth import router as auth_router

# ── Application ──────────────────────────────────────────────────
app = FastAPI(
    title="RouteZone API",
    description="""
API REST du projet RouteZone -- prediction de gravite des accidents routiers.
Certification RNCP37827 Dev IA Simplon x Microsoft.

**Domaines :**
- `/accidents`, `/meteo`, `/onisr` -- donnees BAAC (C5)
- `/predict`, `/predictions` -- intelligence artificielle (C8-C9)
- `/auth` -- authentification JWT

**Authentification :** header `X-API-Key` et/ou `Authorization: Bearer <JWT>`
    """,
    version="2.0.0",
)

logger.info("API RouteZone demarree")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# ── Routers ──────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(data_router)
app.include_router(ia_router)


# ── Health check ─────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def accueil():
    """Health check -- verifie que l'API est en ligne."""
    from routes_ia import MODEL_VERSION, features, calibrator
    return {
        "message": "RouteZone API",
        "status": "ok",
        "version": "2.0.0",
        "model_version": MODEL_VERSION,
        "features_count": len(features),
        "calibrated": calibrator is not None,
        "documentation": "/docs",
        "routes": {
            "donnees": ["/accidents", "/accidents/stats", "/accidents/departement/{dep}",
                        "/accidents/gravite", "/meteo/stats", "/onisr/barometre"],
            "ia": ["/predict", "/predictions"],
            "auth": ["/auth/register", "/auth/login", "/auth/me"],
        }
    }

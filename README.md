# RouteZone

**Prediction de la gravite des accidents routiers en France metropolitaine**

Projet de certification RNCP37827 -- Developpeur en Intelligence Artificielle -- Simplon x Microsoft

---

## Presentation

RouteZone predit si un accident routier est **grave** (tue ou hospitalise) ou **pas grave** (indemne ou blesse leger), a partir des donnees BAAC 2022-2024.

Le projet integre une analyse du "golden hour" : correlation prouvee (p < 1e-26 en V3 OSRM) entre le temps d'intervention des secours et le taux de deces.

**Modele en production : V3 OSRM** (LightGBM, recall 0.78, AUC 0.857, gap train-test +4.25%).
Les features de temps d'intervention sont calculees avec OSRM (vrais temps routiers,
153 054 accidents enrichis), remplacant l'approximation Haversine x 1.3 de la V2.

---

## Architecture

```mermaid
graph TB
    subgraph Sources["Sources de donnees"]
        BAAC["BAAC 2022-2024<br/>413 570 accidents"]
        METEO["Open-Meteo API"]
        ONISR["ONISR scraping"]
        HOSP["data.gouv.fr<br/>638 SAU"]
        CASERNES["casernes_france.csv<br/>5 906 CIS"]
    end

    subgraph Notebooks["Notebooks"]
        NB01["01 Exploration"]
        NB02["02 API Meteo"]
        NB03["03 Scraping ONISR"]
        NB04["04 Temps intervention<br/>Golden Hour + comparaison Hav/OSRM"]
        NB05["05 Modelisation V1<br/>(original)"]
        NB06["06 MLflow tuning V1<br/>(original)"]
        NB07["07 Modelisation V2<br/>Veille desequilibre Haversine"]
        NB08["08 Modelisation V3<br/>OSRM + Optuna recall+ES"]
    end

    subgraph Infra["Infrastructure"]
        PG[("PostgreSQL 16")]
        OSRM["OSRM Docker<br/>routage temps reel"]
        MODELS["models/*.pkl"]
    end

    subgraph API["API FastAPI :8001"]
        AUTH["/auth"]
        DATA["/accidents /meteo /onisr"]
        IA["/predict /predictions"]
    end

    subgraph Frontend["Streamlit :8501"]
        LOGIN["Login"]
        FORM["Formulaire"]
        MAP["Carte Leaflet"]
        HIST["Historique"]
    end

    BAAC --> NB01
    METEO --> NB02
    ONISR --> NB03
    HOSP & CASERNES --> NB04
    NB01 & NB02 & NB03 & NB04 --> NB05 --> NB06 --> NB07 --> MODELS

    PG --> DATA
    MODELS --> IA
    IA --> PG
    FORM --> OSRM --> IA --> MAP
```

---

## Pipeline ETL

```mermaid
flowchart LR
    subgraph Collecte["1 - Collecte"]
        A1["CSV BAAC<br/>4 fichiers"]
        A2["API Open-Meteo"]
        A3["Site ONISR"]
        A4["data.gouv.fr<br/>638 SAU"]
        A5["casernes_france.csv<br/>5 906 CIS"]
    end

    subgraph Transform["2 - Transformation"]
        B1["Nettoyage<br/>doublons, NaN"]
        B2["Binarisation<br/>GRAVE / PAS GRAVE"]
        B3["Feature engineering"]
        B4["Haversine x 1.3<br/>caserne -> accident -> SAU"]
    end

    subgraph Load["3 - Chargement"]
        C1[("PostgreSQL")]
        C2["CSV processed"]
    end

    A1 --> B1 --> B2 --> C2
    A2 --> C1
    A3 --> C1
    A4 & A5 --> B4 --> C2
    C2 --> B3
```

---

## Parcours utilisateur

```mermaid
flowchart TB
    START(("Utilisateur")) --> LOGIN{"Compte ?"}
    LOGIN -- Non --> REGISTER["Inscription"]
    LOGIN -- Oui --> SIGNIN["Connexion"]
    REGISTER & SIGNIN --> JWT["JWT token"]

    JWT --> FORM["Formulaire<br/>dont lat/lon"]
    FORM --> OSRM["OSRM Docker<br/>3 centres les plus proches<br/>vrais temps routiers"]
    OSRM --> PREDICT["POST /predict<br/>37 features"]
    PREDICT --> RESULT["GRAVE / PAS GRAVE<br/>+ probabilite"]
    RESULT --> CARTE["Carte Leaflet<br/>accident + itineraires"]
    PREDICT --> SAVE["Sauvegarde BDD"]

    CARTE --> NEXT{"Suite ?"}
    NEXT -- Historique --> TABLE["Tableau predictions"]
    NEXT -- Nouvelle --> FORM

    style OSRM fill:#059669,color:#fff
    style PREDICT fill:#7c3aed,color:#fff
    style CARTE fill:#1e40af,color:#fff
```

---

## Pipeline ML

```mermaid
flowchart TB
    DATA["dataset 413 570 lignes<br/>+ temps_intervention.csv"]
    DATA --> FE["Feature Engineering<br/>37 features"]
    FE --> SPLIT["Split temporel<br/>AVANT imputation<br/>34 features"]

    SPLIT --> TRAIN["Train 2022-2023<br/>265 064"]
    SPLIT --> TEST["Test 2024<br/>148 506"]

    TRAIN --> IMPUTE["Imputation<br/>stats TRAIN uniquement"]
    IMPUTE --> TRAIN2["Train impute"]
    IMPUTE --> TEST2["Test impute"]
    TRAIN2 --> SPLIT2["Core 85% / Val 15%"]

    SPLIT2 --> CORE["Train core"]
    SPLIT2 --> VAL["Validation reelle"]
    CORE --> OPTUNA["Optuna 50 trials<br/>class_weight=balanced"]
    OPTUNA --> MODEL["LightGBM"]
    MODEL --> EVAL["Evaluation test 2024"]
    TEST2 --> EVAL
    VAL --> CALIB["Calibration isotonic"]
    MODEL --> CALIB

    style SPLIT fill:#dc2626,color:#fff
    style IMPUTE fill:#1e40af,color:#fff
    style CALIB fill:#059669,color:#fff
```

---

## Golden Hour

Correlation prouvee entre temps d'intervention et deces (72 123 blesses graves).

**V2 Haversine x 1.3** (approximation) :

| Temps total | Taux deces | n |
|---|---|---|
| < 5 min | **10.0%** | 14 252 |
| 10-15 min | 14.7% | 9 677 |
| 20-30 min | 16.5% | 15 465 |
| > 30 min | **17.4%** | 10 444 |

Chi2 p = 5.8e-20.

**V3 OSRM** (mesure routiere reelle, 153 054 accidents) :

| Temps total | Taux deces | n |
|---|---|---|
| < 5 min | **8.2%** | 936 |
| 10-15 min | 12.4% | 14 287 |
| 20-30 min | 16.0% | 20 034 |
| > 30 min | **17.3%** | 12 172 |

Chi2 p = **6.6e-27** (effet renforce, +38% vs V2).

OSRM revele aussi **+47% de zones blanches** que Haversine ne voyait pas
(11 102 -> 16 305 accidents avec temps total > 30 min).

---

## Resultats (test 2024, 148 506 usagers)

**Modele V3 OSRM final** (deploye dans l'API + Streamlit) :

```
              precision    recall  f1-score   support
   Pas grave       0.94      0.77      0.85    123 037
       Grave       0.41      0.78      0.54     25 469
   macro avg       0.68      0.77      0.69    148 506
```

Comparaison historique :

| Metrique | V1* | V2 Haversine | V3 OSRM | Best |
|---|---:|---:|---:|---|
| Recall | 0.805 | 0.784 | **0.780** | ~ V2 |
| Precision | 0.390 | 0.405 | **0.409** | V3 |
| **F1 macro** | 0.676 | 0.689 | **0.691** | V3 |
| **AUC-ROC** | 0.850 | 0.855 | **0.857** | V3 |
| Gap train-test recall | ? | +9.7% | **+4.25%** | V3 |

*V1 : data leakage (split aleatoire + imputation globale)*

**34 features V3.** Top : `temps_total_osrm` (rang #1 en V3, vs rang #4 en V2),
catv, age, col, vma. La feature OSRM **devient l'information la plus discriminante**
du modele.

### Comparaison des 3 strategies V3

| Approche | Recall | AUC | Gap train-test | Verdict |
|---|---:|---:|---:|---|
| V3 vanilla (defaults) | 0.7591 | 0.8554 | +9.7% | Leger overfit |
| V3 Optuna scoring=AUC | 0.7397 | 0.8544 | +14.5% | Pire (AUC ne penalise pas le gap) |
| **V3 Optuna scoring=recall + early stopping** | **0.7802** | **0.8569** | **+4.25%** | **Retenu** |

Hyperparametres V3 final : `max_depth=9`, `learning_rate=0.012`, `num_leaves=45`,
`min_child_samples=153`, `subsample=0.74`, `colsample_bytree=0.65`,
`n_estimators=1000` avec early stopping (patience=50 sur val).

---

## Veille desequilibre

| Strategie | Recall test | Verdict |
|---|---|---|
| **class_weight="balanced"** | **0.784** | **Retenu -- stable** |
| SMOTE-NC | 0.613 | Overfitting |
| Baseline | faible | -- |
| Threshold 0.35 | haut recall, basse precision | -- |

---

## Flux JWT

```mermaid
sequenceDiagram
    participant S as Streamlit
    participant OSRM as OSRM Docker
    participant API as API :8001
    participant DB as PostgreSQL

    S->>API: POST /auth/login
    API->>DB: Verify bcrypt
    API-->>S: JWT

    S->>OSRM: Route vers 3 centres
    OSRM-->>S: Temps + traces

    S->>API: POST /predict (JWT + 37 features)
    API->>API: LightGBM inference
    API->>DB: INSERT predictions
    API-->>S: label + probability

    S->>S: Carte Leaflet
```

---

## Schema BDD

```mermaid
erDiagram
    accidents ||--o{ usagers : num_acc
    accidents ||--o{ meteo : num_acc
    accidents ||--o{ temps_intervention : num_acc
    users ||--o{ predictions : user_id

    accidents {
        text num_acc PK
        int jour
        int mois
        int an
        float lat
        float long
        text dep
    }

    temps_intervention {
        text num_acc PK
        float nearest_pompiers_min
        float nearest_sau_min
        float temps_total_prise_en_charge
    }

    users {
        serial id PK
        text email UK
        text password_hash
    }

    predictions {
        serial id PK
        int user_id FK
        timestamp created_at
        int prediction
        float probability
    }
```

---

## Structure du projet

```
routezone/
├── bdd/
│   ├── create_db.sql                       # 8 tables + index
│   └── import_data.py                      # Import CSV -> PostgreSQL
├── data/
│   ├── raw/
│   │   └── casernes_france.csv             # 5 906 CIS
│   └── processed/
│       ├── dataset_clean.csv
│       ├── centres_urgences.csv            # 638 SAU (emergency=yes)
│       └── temps_intervention.csv          # 413K temps (5 features)
├── docker/
│   ├── Dockerfile.api
│   └── requirements_api.txt
├── models/                                 # Artefacts ML
├── notebooks/
│   ├── 01_exploration                      # EDA, nettoyage
│   ├── 02_api_meteo                        # Enrichissement meteo
│   ├── 03_scraping_onisr                   # Scraping ONISR
│   ├── 04_temps_intervention               # SAU + casernes + golden hour
│   │                                       # + comparaison Haversine vs OSRM (cells 25-32)
│   ├── 05_modelisation_v1                  # Baseline RF, XGB, LightGBM (original Meriem)
│   ├── 06_mlflow_tuning_v1                 # Optuna V1 (original Meriem)
│   ├── 07_modelisation_v2                  # Veille desequilibre + Haversine
│   └── 08_modelisation_v3_osrm             # V3 OSRM + Optuna recall+ES
├── src/
│   ├── api/                                # API unifiee FastAPI
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── security.py                     # API key + JWT + bcrypt
│   │   ├── routes_data.py                  # /accidents, /meteo, /onisr
│   │   ├── routes_ia.py                    # /predict (auto-load V3 si dispo, sinon V2)
│   │   └── routes_auth.py                  # /auth/*
│   ├── app.py                              # Streamlit + Folium + OSRM
│   └── scripts/
│       ├── enrich_osrm_batch.py            # Orchestrateur Docker region par region
│       ├── train_v3_optuna_final.py        # Retrain V3 final (script)
│       ├── optuna_v3_recall_es.py          # Optuna V3 (recall + early stopping)
│       ├── check_overfit_v3.py             # Verif gap train/val/test
│       └── run_comparison_v2.py            # Comparaison Hav vs OSRM (offline)
├── tests/test_api.py
├── docker-compose.yml                      # PostgreSQL + OSRM + API
├── osrm_prepare.bat                        # Pre-prep OSRM (regions Geofabrik)
├── .env
└── requirements.txt
```

---

## Lancement

### Premiere installation

```bash
git clone https://github.com/Meriem69/Routezone.git
cd routezone
cp .env.example .env

# Lancer les services (PostgreSQL + API)
docker-compose up -d

# Importer les donnees
python bdd/import_data.py

# Executer les notebooks 01 a 07 dans Jupyter

# (Optionnel mais recommande pour V3)
# Enrichir le dataset avec les vrais temps OSRM (~2h, 22 regions Geofabrik)
python src/scripts/enrich_osrm_batch.py --regions all --keep-pbf

# Entrainer le modele V3 OSRM (~10 min Optuna 30 trials + ES)
python src/scripts/optuna_v3_recall_es.py
# -> sauvegarde models/best_model_v3_osrm.pkl
# -> l'API V3 sera auto-chargee au prochain redemarrage

# Redemarrer l'API pour charger V3
docker-compose restart api

# Lancer l'interface (utilise OSRM live pour les temps d'intervention)
streamlit run src/app.py
```

### Lancement quotidien

```bash
docker-compose up -d
streamlit run src/app.py
```

### Verification

```bash
curl http://localhost:8001/       # Health check
curl http://localhost:8001/docs   # Swagger
pytest tests/ -v                  # Tests
```

---

## Endpoints (port 8001)

| Route | Auth | Description |
|-------|------|-------------|
| `GET /` | Public | Health check |
| `POST /auth/register` | Public | Inscription |
| `POST /auth/login` | Public | Connexion |
| `GET /auth/me` | JWT | Infos user |
| `GET /accidents` | API Key | Liste filtrable |
| `GET /accidents/stats` | API Key | Statistiques |
| `GET /accidents/departement/{dep}` | API Key | Par departement |
| `GET /accidents/gravite` | API Key | Repartition |
| `GET /meteo/stats` | API Key | Stats meteo |
| `GET /onisr/barometre` | API Key | Barometre |
| `POST /predict` | API Key ou JWT | Prediction |
| `GET /predictions` | JWT | Historique |

---

## Securite

| Mesure | Implementation |
|--------|---------------|
| Mots de passe | bcrypt |
| Tokens | JWT HS256 |
| Cle API | hmac.compare_digest |
| Auth /predict | API key **ou** JWT |
| Secrets | .env hors du repo |
| Docker | User non-root |

---

## Stack technique

| Composant | Technologie |
|-----------|------------|
| API | FastAPI, APIRouter |
| BDD | PostgreSQL 16, SQLAlchemy |
| Auth | JWT (python-jose), bcrypt |
| ML | LightGBM, Optuna |
| Routage | OSRM Docker |
| Carte | Folium, streamlit-folium |
| Frontend | Streamlit |
| Tracking | MLflow |
| Tests | pytest, TestClient |

---

## Competences RNCP37827

| Code | Competence | Livrable |
|------|-----------|---------|
| C1 | Collecte multi-sources | notebooks 01-04 |
| C2 | Requetes SQL | routes_data.py |
| C3 | Nettoyage et transformation | notebooks 01, 04 |
| C4 | Base de donnees | create_db.sql, PostgreSQL |
| C5 | API REST securisee | routes_data.py |
| C8-C9 | Service IA + API IA | routes_ia.py, notebook 07 |
| C10 | Application IA | app.py |

---

## Auteure

**Meriem Abdelouahed** -- Formation Developpeur IA -- Simplon x Microsoft -- 2026

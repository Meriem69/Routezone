# Prompt de travail RouteZone -- pour Meriem

## Contexte

Projet de certification RNCP37827 (Dev IA, Simplon x Microsoft). Prediction de gravite des accidents routiers (GRAVE vs PAS GRAVE) a partir des donnees BAAC 2022-2024.

---

## Etat du projet de base (avant intervention)

- Notebooks Jupyter (01 exploration, 02 meteo, 03 scraping, 04 modelisation, 05 mlflow)
- 2 APIs FastAPI separees (donnees port 8000, IA port 8001)
- Interface Streamlit (bug : pas d'envoi de cle API)
- Base SQLite
- Tests pytest avec httpx (necessitaient un serveur lance)
- Docker-compose basique sans healthcheck
- Modele LightGBM V1 : recall 0.805 (data leakage probable)

---

## Ce qui a ete fait

### 1. Corrections de bugs
- Streamlit n'envoyait pas le header X-API-Key -> 403 systematique
- Connexions BDD jamais fermees en cas d'erreur
- Comparaison de cle API vulnerable aux timing attacks (`!=` -> `hmac.compare_digest`)

### 2. Migration SQLite -> PostgreSQL
- Schema 8 tables + index
- SQLAlchemy + pool de connexions
- Docker postgres:16-alpine avec healthcheck

### 3. Fusion des 2 APIs en 1 seule
- 1 API FastAPI avec APIRouter par domaine
- `routes_data.py` : /accidents, /meteo, /onisr (C5)
- `routes_ia.py` : /predict, /predictions (C8-C9)
- `routes_auth.py` : /auth (JWT)
- `security.py` : API key + JWT + bcrypt (partage)
- `db.py` : engine SQLAlchemy (partage)
- Auth /predict : accepte API key **ou** JWT

### 4. Authentification JWT + historique
- Table `users` (bcrypt), table `predictions` (auto-save)
- Streamlit : sidebar login/inscription, page historique

### 5. Feature engineering (25 -> 37 features)
- creneau, age_tranche, jour_semaine, is_weekend
- vma_x_nuit, jeune_2roues, pluie_x_surface
- nearest_pompiers_min, nearest_sau_min, temps_intervention_min
- temps_total_prise_en_charge, zone_blanche

### 6. Centres d'urgence + temps d'intervention
- **638 SAU** (emergency=yes) depuis data.gouv.fr
- **5 906 casernes** depuis casernes_france.csv (98 departements)
- Calcul : caserne -> accident (pompiers) + accident -> SAU (evacuation)
- Haversine x 1.3, 60 km/h, 413 570 accidents enrichis
- OSRM Docker pour calcul temps reel dans Streamlit

### 7. Golden Hour (trouvaille cle)
Correlation prouvee (p < 1e-20) entre temps d'intervention et deces :
- < 5 min total : **10.0%** deces
- > 30 min total : **17.4%** deces
- Un blesse grave pris en charge en < 5 min a ~40% de chances en moins de mourir

### 8. Correction data leakage
- Split temporel (train 2022-23, test 2024) AVANT imputation
- Imputation sur stats train uniquement
- Calibration sur validation reelle (pas SMOTE)

### 9. Veille desequilibre (notebook_07)
- 6 strategies testees dans MLflow
- SMOTE-NC : overfitting prouve (recall CV 0.83, test 0.61)
- class_weight="balanced" retenu (stable)

### 10. Carte interactive Streamlit
- Calcul OSRM temps reel avant prediction
- Carte Leaflet : accident (rouge) + 3 centres + itineraires traces
- Legende avec prediction + probabilite + temps

### 11. Reorganisation
- Notebooks = source unique (plus de scripts dupliques)
- Ordre logique : enrichissements (01-04) puis modelisation (05-07)
- 1 seul Dockerfile, 1 seul requirements
- Docker-compose : PostgreSQL + OSRM + API

### 12. Modele V3 OSRM (vrais temps routiers, +1 notebook)

**Probleme identifie sur la V2 :** la feature `temps_total_prise_en_charge` etait calculee
avec **Haversine x 1.3** (approximation distance vol d'oiseau x detour moyen 30%).
C'est une approximation grossiere, surtout en zone rurale ou les routes sont sinueuses.

**Solution : enrichir les 153 054 accidents (avec GPS) avec les vrais temps OSRM.**

#### 12.1 Orchestrateur batch ([src/scripts/enrich_osrm_batch.py](src/scripts/enrich_osrm_batch.py))

OSRM-extract sur la France entiere demande ~24-32 Go de RAM (impossible avec 16 Go).
Solution : traiter chaque region Geofabrik separement.

Pour chaque region (alsace, aquitaine, ... 22 regions) :
1. Telecharger le PBF Geofabrik
2. `osrm-extract` + `osrm-partition` + `osrm-customize` (Docker, ~3-5 Go RAM)
3. Lancer `osrm-routed` en daemon
4. Pour chaque accident de la region :
   - Pre-filtrer top-10 pompiers + top-10 SAU les plus proches en Haversine
   - 1 appel `/table` OSRM (1 source, 20 destinations)
   - Garder min(pompiers) et min(SAU) en temps routier reel
5. Sauvegarder CSV regional (idempotent : reprenable si interruption)
6. Stop OSRM, passe a la region suivante

**Resultat (~2h20 de compute)** : `data/processed/temps_intervention_osrm.csv`
contient pour chaque accident `nearest_pompiers_min_osrm`, `nearest_sau_min_osrm`,
`temps_total_osrm`, **et les valeurs Haversine equivalentes** (`*_hav`) pour comparer.

#### 12.2 Findings de la comparaison Haversine vs OSRM

Sur 153 054 accidents :

| Metrique | Haversine x 1.3 | OSRM reel | Delta |
|---|---:|---:|---:|
| Mediane temps total | ~9 min | ~14 min | +5.6 min |
| Correlation Hav <-> OSRM | -- | -- | 0.887 |
| Zones blanches (>30 min) | 11 102 (7.25%) | **16 305 (10.65%)** | **+47%** |
| Golden Hour Chi2 (graves) | 83.7 (p=5.8e-20) | **115.3 (p=6.6e-27)** | +38% |

**Conclusion** : Haversine x 1.3 sous-estime systematiquement de **5.6 min en mediane**,
masquant **5 203 zones blanches reelles**. OSRM **renforce** la decouverte
Golden Hour, ne la remet pas en cause.

#### 12.3 Notebook 08 -- Retrain V3 OSRM ([notebooks/notebook_08_modelisation_v3_osrm.ipynb](notebooks/notebook_08_modelisation_v3_osrm.ipynb))

V3 utilise les memes 32 features que V2 + remplace les 2 features intervention :
- `temps_total_prise_en_charge` (Haversine) -> `temps_total_osrm`
- `zone_blanche` -> `zone_blanche_osrm`

**Iteration 1 (vanilla)** : LightGBM avec defaults raisonnables.
- Resultat : recall test 0.7591, AUC 0.8554
- **Probleme** : gap train-test recall = +9.7% -> leger overfit

**Iteration 2 (Optuna scoring=AUC, 50 trials)** : optimise AUC en CV.
- Best params trouves : tres faible regularisation
- Resultat : recall test 0.7397 (pire), gap +14.5% (overfit aggrave)
- **Lecon** : optimiser AUC en CV ne penalise PAS le gap train-test.

**Iteration 3 (Optuna scoring=recall + early stopping, 30 trials)** :
- Optimise le **recall** sur validation reelle
- `n_estimators=1000` avec early stopping (patience=50) -> auto-regularisation
- Best params : `max_depth=9`, `lr=0.012`, `num_leaves=45`,
  `min_child_samples=153`, `subsample=0.74`, `colsample=0.65`
- **Resultat retenu** :

| Split | recall | precision | f1_macro | auc |
|---|---:|---:|---:|---:|
| Train (225 304) | 0.8228 | 0.4310 | 0.7081 | 0.8763 |
| Val (39 760) | 0.8034 | 0.4225 | 0.7004 | 0.8653 |
| **Test 2024 (148 506)** | **0.7802** | **0.4090** | **0.6914** | **0.8569** |

**Gap train-test recall = +4.25%** (vs +9.7% vanilla, +14.5% Optuna AUC) -> OK.

#### 12.4 Feature importance V3

`temps_total_osrm` devient la feature **#1 sur 34** (importance 5059).
En V2 Haversine, `temps_total_prise_en_charge` etait #4. **L'apport de la qualite
de la donnee est donc tres important** : le modele "voit" mieux le signal Golden Hour
quand on lui donne le vrai temps routier.

#### 12.5 Integration produit

- **API** [src/api/routes_ia.py](src/api/routes_ia.py) : auto-load V3 si dispo,
  fallback V2 sinon. Le schema d'entree accepte `nearest_pompiers_min` et
  `nearest_sau_min` en optionnel ; si fournis, l'API les utilise comme features
  OSRM. Sinon fallback Haversine (compat retro).
- **Streamlit** [src/app.py](src/app.py) : envoie maintenant les temps OSRM
  reels dans le payload `/predict`. La carte Leaflet montre les vraies routes.
- **Story certif** : "Notre modele de prod utilise OSRM en temps reel pour
  calculer les temps d'intervention au moment de la prediction. Le modele
  est entraine sur 153 054 accidents enrichis OSRM. La comparaison avec
  Haversine quantifie l'apport de la qualite de la donnee."

#### 12.6 Methodologie demontree (a reprendre devant le jury)

1. **Identification d'une approximation** dans la V2 (Haversine x 1.3)
2. **Quantification de l'erreur** : +5.6 min mediane, +47% de zones blanches manquees
3. **Mise en place d'une solution scalable** : batch region par region pour
   tenir dans 16 Go RAM (impossibilite OSRM France entiere)
4. **Re-entrainement avec la meilleure donnee** (V3 OSRM)
5. **Detection d'un overfit** sur V3 vanilla (gap +9.7%)
6. **Iteration sur Optuna** : montrer qu'optimiser AUC peut paradoxalement
   aggraver l'overfit (+14.5%) -> revoir la fonction objective
7. **Solution finale** : Optuna scoring=recall + early stopping (gap +4.25%)
8. **Integration end-to-end** : API + Streamlit utilisent V3 + OSRM live

---

## Structure du projet

```
routezone/
├── bdd/
│   ├── create_db.sql
│   └── import_data.py
├── data/
│   ├── raw/casernes_france.csv           # 5 906 CIS
│   └── processed/
│       ├── dataset_clean.csv
│       ├── centres_urgences.csv          # 638 SAU
│       └── temps_intervention.csv        # 413K (5 features)
├── docker/
│   ├── Dockerfile.api
│   └── requirements_api.txt
├── models/
├── notebooks/
│   ├── 01_exploration
│   ├── 02_api_meteo
│   ├── 03_scraping_onisr
│   ├── 04_temps_intervention             # SAU + casernes + golden hour
│   │                                     # + cells 25-32 : comparaison Hav vs OSRM
│   ├── 05_modelisation_v1                # Baseline (original Meriem)
│   ├── 06_mlflow_tuning_v1               # Optuna V1 (original Meriem)
│   ├── 07_modelisation_v2                # Veille + ROC + SHAP (Haversine)
│   └── 08_modelisation_v3_osrm           # V3 OSRM + Optuna recall+ES
├── src/
│   ├── api/ (main, db, security, routes_data, routes_ia, routes_auth)
│   ├── app.py                            # Streamlit + Folium + OSRM live
│   └── scripts/
│       ├── enrich_osrm_batch.py          # 22 regions Geofabrik -> CSV OSRM
│       ├── optuna_v3_recall_es.py        # Train V3 final (Optuna + ES)
│       ├── train_v3_optuna_final.py      # Variante Optuna AUC (overfit +14.5%)
│       ├── check_overfit_v3.py           # Audit train/val/test
│       └── run_comparison_v2.py          # Stats Hav vs OSRM (offline)
├── tests/test_api.py
├── docker-compose.yml                    # PostgreSQL + OSRM + API
└── .env
```

---

## Stack technique

| Composant | Technologie |
|-----------|------------|
| API | FastAPI, APIRouter |
| BDD | PostgreSQL 16, SQLAlchemy |
| Auth | JWT, bcrypt |
| ML | LightGBM, Optuna, class_weight="balanced" |
| Routage | OSRM Docker |
| Carte | Folium, streamlit-folium |
| Frontend | Streamlit |
| Tracking | MLflow |
| Tests | pytest, TestClient |

---

## Lancement

```bash
# Premiere fois (~3h au total avec V3)
docker-compose up -d                                                    # PostgreSQL + API
python bdd/import_data.py                                               # Import donnees
# Executer notebooks 01 a 07 (modelisation V2 Haversine)

# V3 OSRM (~2h20 batch + 10 min retrain) :
python src/scripts/enrich_osrm_batch.py --regions all --keep-pbf        # Enrichissement OSRM
python src/scripts/optuna_v3_recall_es.py                               # Optuna V3 + train final
docker-compose restart api                                              # API auto-load V3

streamlit run src/app.py                                                # Interface

# Quotidien
docker-compose up -d
streamlit run src/app.py
```

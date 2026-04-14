# 🛣️ RouteZone

**Prédiction de la gravité des accidents routiers en France métropolitaine**

Projet de certification RNCP37827 — Développeur en Intelligence Artificielle — Simplon x Microsoft

---

## 📌 Présentation

RouteZone est un système de machine learning qui prédit si un accident routier est **grave** (tué ou hospitalisé) ou **pas grave** (indemne ou blessé léger), à partir des données officielles BAAC 2022-2024 publiées par le Ministère de l'Intérieur.

**Modèle retenu :** LightGBM optimisé Optuna — Recall GRAVE : **0.805** — AUC-ROC : **0.850**

---

## 🗂️ Structure du projet

```
routezone/
├── bdd/                  ← Modèle Merise, scripts SQL, base SQLite
│   ├── create_db.sql
│   ├── import_data.py
│   ├── schema_merise.md
│   └── MCD.PNG
├── data/
│   ├── raw/              ← CSV BAAC 2022-2024 (non versionnés)
│   └── processed/        ← Datasets nettoyés (non versionnés)
├── docs/                 ← Rapports de certification
├── models/               ← Modèles entraînés .pkl (non versionnés)
├── notebooks/
│   ├── notebook_01_exploration.ipynb
│   ├── notebook_02_api_meteo.ipynb
│   ├── notebook_03_scraping_onisr.ipynb
│   ├── notebook_04_modelisation.ipynb
│   ├── notebook_05_mlflow_optuna.ipynb
│   └── visualisations/
├── src/
│   ├── api_data/         ← FastAPI données (port 8000)
│   ├── api_ia/           ← FastAPI IA — /predict (port 8001)
│   ├── scripts/          ← collect_meteo.py, scraping_onisr.py
│   └── app.py            ← Interface Streamlit
├── tests/                ← Tests pytest
├── requirements.txt
└── README.md
```

---

## 🚀 Installation et lancement

### 1. Cloner le repo et créer l'environnement

```bash
git clone https://github.com/Meriem69/Routezone.git
cd routezone
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Initialiser la base de données

```bash
cd bdd
python import_data.py        # importe les CSV BAAC dans SQLite
python ../src/scripts/collect_meteo.py    # enrichissement météo (optionnel)
python ../src/scripts/scraping_onisr.py   # scraping ONISR (optionnel)
```

### 3. Lancer les APIs

```bash
# Terminal 1 — API données (port 8000)
cd src/api_data
uvicorn main:app --reload

# Terminal 2 — API IA (port 8001)
cd src/api_ia
uvicorn main:app --reload --port 8001
```

### 4. Lancer l'interface Streamlit

```bash
cd src
streamlit run app.py
```

---

## 🔐 Authentification

Tous les endpoints (sauf `/`) nécessitent le header `X-API-Key` :

```bash
curl -H "X-API-Key: routezone-secret-2024" http://localhost:8000/accidents/stats
```

Documentation interactive disponible sur `http://localhost:8000/docs`

---

## 📊 Données

| Source | Description | Volume |
|--------|-------------|--------|
| BAAC 2022-2024 | Accidents corporels — data.gouv.fr | 413 570 lignes |
| API Open-Meteo | Météo historique heure par heure | ~500 accidents enrichis |
| ONISR baromètre | Tués mensuels — scraping | 30 baromètres |

---

## 🤖 Résultats du modèle

| Méthode | F1 macro | AUC-ROC | Recall GRAVE |
|---------|----------|---------|--------------|
| Tuning manuel | 0.683 | 0.853 | 0.800 |
| GridSearch | 0.683 | 0.854 | 0.799 |
| Optuna F1 macro | 0.716 | 0.866 | 0.768 |
| **Optuna Recall ✓** | **0.676** | **0.850** | **0.805** |

Le modèle retenu maximise le **Recall GRAVE** : dans un contexte de sécurité routière, rater un accident grave est plus dangereux qu'une fausse alarme.

---

## 🏗️ Compétences certification

| Compétence | Description | Livrable |
|-----------|-------------|---------|
| C1 | Collecte multi-sources | notebooks 01-03, scripts |
| C2 | Requêtes SQL | api_data/main.py, notebooks |
| C3 | Nettoyage et transformation | notebook_01, dataset_clean.csv |
| C4 | Base de données + RGPD | bdd/, schema_merise.md |
| C5 | API REST sécurisée | src/api_data/main.py |
| C8-C9 | Service IA + API IA | src/api_ia/main.py |
| C10 | Application IA | src/app.py |

---

## 👩‍💻 Auteure

**Meriem Abdelouahed** — Formation Développeur IA — Simplon x Microsoft — 2026

"""
Genere notebooks/notebook_08_modelisation_v3_osrm.ipynb : retrain avec
les vrais temps OSRM (au lieu de Haversine V2). Compare V2 vs V3 cote-a-cote.
"""
import json
from pathlib import Path

NB_PATH = Path(__file__).resolve().parent.parent.parent / "notebooks" / "notebook_08_modelisation_v3_osrm.ipynb"


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src.splitlines(keepends=True)}


CELLS = [
    md("""# Notebook 08 -- Modelisation V3 : temps d'intervention OSRM reels

**Objectif :** Reentrainer le modele LightGBM avec les vrais temps routiers OSRM
au lieu de l'approximation Haversine x 1.3 utilisee dans la V2. Comparer V2 et V3
cote-a-cote (metriques, feature importance, SHAP).

**Hypothese :** les temps OSRM reels (variation +5 min mediane vs Haversine en zone
rurale, +0 min en zone urbaine) doivent ameliorer le pouvoir predictif sur les
accidents en zones blanches reelles.

**Plan :**
1. Imports et configuration
2. Chargement + features V3 (temps_total_osrm + zone_blanche_osrm)
3. Entrainement final (memes hyperparametres que V2, class_weight="balanced")
4. Comparaison V2 vs V3 (metriques + ROC + feature importance)
5. SHAP V3
6. Sauvegarde modele V3
"""),

    md("## 1. Imports et configuration"),

    code("""import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from pathlib import Path
from datetime import datetime

from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, roc_curve,
    f1_score, recall_score, precision_score
)
from sklearn.calibration import CalibratedClassifierCV
import lightgbm as lgb
import mlflow
import mlflow.sklearn

warnings.filterwarnings("ignore")
plt.style.use("seaborn-v0_8-darkgrid")
plt.rcParams["figure.figsize"] = (12, 6)

ROOT = Path(".").parent
DATA_PATH = ROOT / "data" / "processed" / "dataset_clean.csv"
INTERV_OSRM_PATH = ROOT / "data" / "processed" / "temps_intervention_osrm.csv"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)
VIZ_DIR = Path("visualisations")
VIZ_DIR.mkdir(exist_ok=True)

mlflow.set_tracking_uri("mlruns")
mlflow.set_experiment("routezone_v3_osrm")

# Pre-requis : avoir tourne `python src/scripts/enrich_osrm_batch.py --regions all`
assert INTERV_OSRM_PATH.exists(), (
    f"Manquant : {INTERV_OSRM_PATH}\\n"
    "Lance d'abord : python src/scripts/enrich_osrm_batch.py --regions all"
)
print("Imports OK")
"""),

    md("""## 2. Chargement + features V3 (temps OSRM)

Difference cle avec notebook 07 : on utilise `temps_total_osrm` (vrai temps routier)
au lieu de `temps_total_prise_en_charge` (Haversine x 1.3).
"""),

    code("""# Chargement + binarisation cible
df = pd.read_csv(DATA_PATH, low_memory=False)
df["target"] = df["grav"].map({1: 0, 4: 0, 2: 1, 3: 1})
df = df.dropna(subset=["target"])
df["target"] = df["target"].astype(int)
print(f"Dataset : {len(df):,} lignes")

# Merge avec temps OSRM
df_ti = pd.read_csv(INTERV_OSRM_PATH).drop_duplicates(subset=["Num_Acc"], keep="first")
key = "Num_Acc" if "Num_Acc" in df.columns else "num_acc"
df = df.merge(df_ti, left_on=key, right_on="Num_Acc", how="left")

print(f"Temps OSRM enrichis : {df['temps_total_osrm'].notna().sum():,}/{len(df):,} "
      f"({df['temps_total_osrm'].notna().mean()*100:.1f}%)")

# Feature engineering V3 : zone_blanche basee sur OSRM
df["zone_blanche_osrm"] = (df["temps_total_osrm"] > 30).astype(int)

# Comparaison rapide V2 vs V3 (avant modelisation)
if "temps_total_hav" in df.columns:
    print(f"\\nMediane temps total (Haversine) : {df['temps_total_hav'].median():.1f} min")
    print(f"Mediane temps total (OSRM)      : {df['temps_total_osrm'].median():.1f} min")
    print(f"Zone blanche selon Haversine    : {(df['temps_total_hav']>30).mean()*100:.2f}%")
    print(f"Zone blanche selon OSRM         : {df['zone_blanche_osrm'].mean()*100:.2f}%")
"""),

    code("""# Feature engineering classique (identique notebook 07)
def get_creneau(h):
    if pd.isna(h): return 2
    h = int(h)
    if 0 <= h <= 6: return 0
    elif 7 <= h <= 9: return 1
    elif 10 <= h <= 16: return 2
    elif 17 <= h <= 21: return 3
    else: return 4

df["creneau"] = df["heure"].apply(get_creneau)

if "age" not in df.columns:
    df["age"] = df.apply(
        lambda r: int(r["an"]) - int(r["an_nais"]) if pd.notna(r.get("an_nais")) else np.nan,
        axis=1)

df["age_tranche"] = df["age"].apply(
    lambda a: 0 if pd.notna(a) and a < 25 else
              (1 if pd.notna(a) and a < 45 else
               (2 if pd.notna(a) and a < 65 else 3)))

if all(c in df.columns for c in ["jour", "mois", "an"]):
    df["jour_semaine"] = df.apply(
        lambda r: datetime(int(r["an"]), int(r["mois"]), int(r["jour"])).weekday()
                  if pd.notna(r["jour"]) else 2, axis=1)
    df["is_weekend"] = (df["jour_semaine"] >= 5).astype(int)

df["vma_x_nuit"] = df["vma"].fillna(50) * (df["lum"].fillna(1) >= 3).astype(int)
df["jeune_2roues"] = ((df["age"].fillna(35) < 25) &
                      (df["catv"].fillna(7).isin([2, 30, 31, 32]))).astype(int)
df["pluie_x_surface"] = ((df["atm"].fillna(1).isin([2, 3])) &
                         (df["surf"].fillna(1).isin([2, 3, 4]))).astype(int)

for col in ["temperature", "precipitation", "windspeed"]:
    if col not in df.columns:
        df[col] = np.nan

if "int" in df.columns:
    df = df.rename(columns={"int": "int_feat"})

print("Features V3 creees")
"""),

    code("""# Selection features V3 + split temporel + imputation safe (identique nb07
# sauf temps_total_osrm + zone_blanche_osrm)
FEATURES = [
    # BAAC originales
    "lum", "agg", "int_feat", "atm", "col", "catr", "circ", "vosp",
    "prof", "plan", "surf", "infra", "situ", "vma",
    "catu", "sexe", "trajet", "secu1", "catv", "age", "heure", "mois",
    # Meteo
    "temperature", "precipitation", "windspeed",
    # Features derivees
    "creneau", "age_tranche", "jour_semaine", "is_weekend",
    "vma_x_nuit", "jeune_2roues", "pluie_x_surface",
    # V3 : OSRM real-time intervention
    "temps_total_osrm", "zone_blanche_osrm",
]
FEATURES = [f for f in FEATURES if f in df.columns]

CATEGORICAL = ["lum", "agg", "atm", "col", "catr", "circ", "vosp", "prof", "plan",
               "surf", "infra", "situ", "catu", "sexe", "trajet", "secu1", "catv",
               "creneau", "age_tranche", "jour_semaine"]
if "int_feat" in FEATURES:
    CATEGORICAL.append("int_feat")
cat_actual = [c for c in CATEGORICAL if c in FEATURES]

mask_train = df["an"].isin([2022, 2023])
mask_test = df["an"] == 2024
df_train, df_test = df[mask_train].copy(), df[mask_test].copy()
print(f"Split temporel : train 2022-2023 ({len(df_train):,}), test 2024 ({len(df_test):,})")

# Imputation SAFE (stats train uniquement)
for col in FEATURES:
    if col in cat_actual:
        fill_val = df_train[col].mode().iloc[0] if not df_train[col].mode().empty else 0
    else:
        fill_val = df_train[col].median() if df_train[col].notna().any() else 0
    df_train[col] = df_train[col].fillna(fill_val)
    df_test[col] = df_test[col].fillna(fill_val)

for col in cat_actual:
    df_train[col] = df_train[col].astype(int).astype("category")
    df_test[col] = df_test[col].astype(int).astype("category")

X_train_full = df_train[FEATURES].copy()
y_train_full = df_train["target"].copy()
X_test = df_test[FEATURES].copy()
y_test = df_test["target"].copy()

X_train, X_val, y_train, y_val = train_test_split(
    X_train_full, y_train_full, test_size=0.15, stratify=y_train_full, random_state=42)

print(f"Train core : {len(X_train):,} | Val : {len(X_val):,} | Test : {len(X_test):,}")
print(f"{len(FEATURES)} features V3")
"""),

    md("""## 3. Entrainement V3 (memes hyperparametres que V2)

On reutilise les hyperparametres optimises Optuna de notebook 07 pour
isoler l'effet du changement de feature (temps OSRM vs Haversine).
"""),

    code("""# Hyperparametres V2 (issus du best Optuna de notebook 07)
# A defaut, on utilise des params raisonnables
params_v3 = {
    "objective": "binary",
    "metric": "binary_logloss",
    "verbosity": -1,
    "boosting_type": "gbdt",
    "n_estimators": 500,
    "max_depth": 10,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 30,
    "class_weight": "balanced",
    "random_state": 42,
}

# Si modele V2 existe, recharger ses hyperparametres pour comparaison fair
v2_params_path = MODELS_DIR / "best_params_v2.pkl"
if v2_params_path.exists():
    v2_params = joblib.load(v2_params_path)
    params_v3.update({k: v for k, v in v2_params.items() if k in params_v3})
    print(f"Hyperparametres reutilises depuis modele V2 : {list(v2_params.keys())}")

with mlflow.start_run(run_name="v3_osrm_class_weight_balanced"):
    mlflow.log_params(params_v3)
    model_v3 = lgb.LGBMClassifier(**params_v3)
    model_v3.fit(X_train, y_train, categorical_feature=cat_actual)

    proba_v3 = model_v3.predict_proba(X_test)[:, 1]
    pred_v3 = (proba_v3 >= 0.5).astype(int)

    metrics_v3 = {
        "recall_grave": recall_score(y_test, pred_v3),
        "precision_grave": precision_score(y_test, pred_v3),
        "f1_macro": f1_score(y_test, pred_v3, average="macro"),
        "auc_roc": roc_auc_score(y_test, proba_v3),
    }
    mlflow.log_metrics(metrics_v3)

print("\\n=== V3 OSRM - Resultats test 2024 ===")
for k, v in metrics_v3.items():
    print(f"  {k:18s} : {v:.4f}")
print()
print(classification_report(y_test, pred_v3, target_names=["Pas grave", "Grave"]))
"""),

    md("## 4. Comparaison V2 vs V3"),

    code("""# Charger modele V2 si dispo
v2_path = MODELS_DIR / "best_model_v2.pkl"
if v2_path.exists():
    model_v2 = joblib.load(v2_path)
    # V2 utilise temps_total_prise_en_charge / zone_blanche, pas dispo dans X_test V3.
    # On prepare un X_test V2 avec les colonnes Haversine.
    df_test_v2 = df_test.copy()
    df_test_v2["temps_total_prise_en_charge"] = df_test_v2.get("temps_total_hav", np.nan)
    df_test_v2["zone_blanche"] = (df_test_v2["temps_total_prise_en_charge"] > 30).astype(int)
    # Imputation pour V2
    for col in df_test_v2.columns:
        if col in ["temps_total_prise_en_charge"]:
            fill = df_test_v2[col].median()
            df_test_v2[col] = df_test_v2[col].fillna(fill)

    # Recuperer features V2 (depuis features_v2.pkl si dispo)
    feat_v2_path = MODELS_DIR / "features_v2.pkl"
    if feat_v2_path.exists():
        FEATURES_V2 = joblib.load(feat_v2_path)
        X_test_v2 = df_test_v2[FEATURES_V2].copy()
        for col in cat_actual:
            if col in X_test_v2.columns:
                X_test_v2[col] = X_test_v2[col].astype(int).astype("category")
        proba_v2 = model_v2.predict_proba(X_test_v2)[:, 1]
        pred_v2 = (proba_v2 >= 0.5).astype(int)
        metrics_v2 = {
            "recall_grave": recall_score(y_test, pred_v2),
            "precision_grave": precision_score(y_test, pred_v2),
            "f1_macro": f1_score(y_test, pred_v2, average="macro"),
            "auc_roc": roc_auc_score(y_test, proba_v2),
        }

        comp = pd.DataFrame({"V2 Haversine": metrics_v2, "V3 OSRM": metrics_v3})
        comp["delta"] = comp["V3 OSRM"] - comp["V2 Haversine"]
        print("Comparaison V2 vs V3 :")
        print(comp.round(4))
    else:
        print("features_v2.pkl introuvable - relance notebook 07 pour generer V2")
else:
    print("best_model_v2.pkl introuvable - retrain V2 d'abord (notebook 07)")
    proba_v2, pred_v2 = None, None
"""),

    code("""# ROC compare V2 vs V3
fig, ax = plt.subplots(figsize=(8, 8))
fpr3, tpr3, _ = roc_curve(y_test, proba_v3)
ax.plot(fpr3, tpr3, lw=2, label=f"V3 OSRM (AUC={metrics_v3['auc_roc']:.3f})", color="#dc2626")
if proba_v2 is not None:
    fpr2, tpr2, _ = roc_curve(y_test, proba_v2)
    ax.plot(fpr2, tpr2, lw=2, label=f"V2 Haversine (AUC={metrics_v2['auc_roc']:.3f})",
            color="#3b82f6", linestyle="--")
ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
ax.set_xlabel("Taux faux positifs")
ax.set_ylabel("Taux vrais positifs")
ax.set_title("ROC Curve : V2 vs V3")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(VIZ_DIR / "viz_nb08_roc_v2_vs_v3.png", dpi=150)
plt.show()
"""),

    code("""# Feature importance V3 (top 15)
importance_v3 = pd.Series(model_v3.feature_importances_, index=FEATURES).sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(10, 8))
top = importance_v3.tail(15)
colors = ["#dc2626" if "osrm" in c else "#f97316" for c in top.index]
ax.barh(top.index, top.values, color=colors)
ax.set_xlabel("Importance (split count)")
ax.set_title("Top 15 features -- LightGBM V3 (rouge = features OSRM)")
plt.tight_layout()
plt.savefig(VIZ_DIR / "viz_nb08_feature_importance_v3.png", dpi=150)
plt.show()

print("\\nPosition des features OSRM dans le top :")
for f in ["temps_total_osrm", "zone_blanche_osrm"]:
    if f in importance_v3.index:
        rank = (importance_v3.index[::-1] == f).argmax() + 1
        print(f"  {f:25s} : rang {rank}/{len(FEATURES)}, importance {importance_v3[f]:,.0f}")
"""),

    md("## 5. SHAP V3 (top contributions)"),

    code("""import shap

X_shap = X_test.sample(min(1000, len(X_test)), random_state=42)
for col in cat_actual:
    if col in X_shap.columns:
        X_shap[col] = X_shap[col].astype(int)

explainer = shap.TreeExplainer(model_v3)
shap_values = explainer.shap_values(X_shap)
shap_vals = shap_values[1] if isinstance(shap_values, list) else shap_values

fig = plt.figure(figsize=(12, 8))
shap.summary_plot(shap_vals, X_shap, feature_names=FEATURES, show=False)
plt.tight_layout()
plt.savefig(VIZ_DIR / "viz_nb08_shap_v3.png", dpi=150, bbox_inches="tight")
plt.show()
"""),

    md("## 6. Sauvegarde modele V3"),

    code("""# Calibration sur validation
calibrator_v3 = CalibratedClassifierCV(model_v3, cv=3, method="isotonic")
calibrator_v3.fit(X_val, y_val)

joblib.dump(model_v3, MODELS_DIR / "best_model_v3_osrm.pkl")
joblib.dump(calibrator_v3, MODELS_DIR / "calibrator_v3_osrm.pkl")
joblib.dump(FEATURES, MODELS_DIR / "features_v3_osrm.pkl")
print(f"Modele V3 sauvegarde dans {MODELS_DIR}/")
"""),

    md("""## 7. Conclusion V3

**Ce qui change vs V2 :**
- Features `temps_total_prise_en_charge` (Haversine x 1.3) -> `temps_total_osrm` (vrai temps routier)
- Feature `zone_blanche` -> `zone_blanche_osrm`

**Ce qui ne change pas :** memes hyperparametres, meme split temporel,
meme imputation, meme `class_weight="balanced"`.

**Story certif :** la difference de metriques entre V2 et V3 quantifie l'apport
de la qualite de la donnee (vrai temps routier vs approximation geographique).
Voir le tableau comparatif ci-dessus.
"""),
]


def main():
    nb = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NB_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"OK -> {NB_PATH.name}  ({len(CELLS)} cellules)")


if __name__ == "__main__":
    main()

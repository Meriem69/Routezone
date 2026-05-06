"""
Verifie l'overfit du modele V3 OSRM : compare metriques train vs val vs test.
Si recall_train >> recall_test, c'est de l'overfit.
"""
from pathlib import Path
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import recall_score, precision_score, f1_score, roc_auc_score, classification_report

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"

print("Reconstruction du dataset V3 (meme split que notebook 08)...")
df = pd.read_csv(DATA_DIR / "dataset_clean.csv", low_memory=False)
df["target"] = df["grav"].map({1: 0, 4: 0, 2: 1, 3: 1})
df = df.dropna(subset=["target"])
df["target"] = df["target"].astype(int)

df_ti = pd.read_csv(DATA_DIR / "temps_intervention_osrm.csv").drop_duplicates("Num_Acc")
key = "Num_Acc" if "Num_Acc" in df.columns else "num_acc"
df = df.merge(df_ti, left_on=key, right_on="Num_Acc", how="left")
df["zone_blanche_osrm"] = (df["temps_total_osrm"] > 30).astype(int)


def get_creneau(h):
    if pd.isna(h): return 2
    h = int(h)
    return [0,0,0,0,0,0,0,1,1,1,2,2,2,2,2,2,2,3,3,3,3,3,4,4][h]

df["creneau"] = df["heure"].apply(get_creneau)
if "age" not in df.columns:
    df["age"] = df.apply(lambda r: int(r["an"]) - int(r["an_nais"]) if pd.notna(r.get("an_nais")) else np.nan, axis=1)
df["age_tranche"] = df["age"].apply(
    lambda a: 0 if pd.notna(a) and a < 25 else (1 if pd.notna(a) and a < 45 else (2 if pd.notna(a) and a < 65 else 3)))
df["jour_semaine"] = df.apply(
    lambda r: datetime(int(r["an"]), int(r["mois"]), int(r["jour"])).weekday() if pd.notna(r["jour"]) else 2, axis=1)
df["is_weekend"] = (df["jour_semaine"] >= 5).astype(int)
df["vma_x_nuit"] = df["vma"].fillna(50) * (df["lum"].fillna(1) >= 3).astype(int)
df["jeune_2roues"] = ((df["age"].fillna(35) < 25) & (df["catv"].fillna(7).isin([2,30,31,32]))).astype(int)
df["pluie_x_surface"] = ((df["atm"].fillna(1).isin([2,3])) & (df["surf"].fillna(1).isin([2,3,4]))).astype(int)
for col in ["temperature","precipitation","windspeed"]:
    if col not in df.columns: df[col] = np.nan
if "int" in df.columns: df = df.rename(columns={"int":"int_feat"})

FEATURES = joblib.load(MODELS_DIR / "features_v3_osrm.pkl")
CATEGORICAL = ["lum","agg","atm","col","catr","circ","vosp","prof","plan","surf","infra","situ",
               "catu","sexe","trajet","secu1","catv","creneau","age_tranche","jour_semaine","int_feat"]
cat_actual = [c for c in CATEGORICAL if c in FEATURES]

mask_train = df["an"].isin([2022, 2023])
mask_test = df["an"] == 2024
df_train, df_test = df[mask_train].copy(), df[mask_test].copy()

for col in FEATURES:
    if col in cat_actual:
        fill = df_train[col].mode().iloc[0] if not df_train[col].mode().empty else 0
    else:
        fill = df_train[col].median() if df_train[col].notna().any() else 0
    df_train[col] = df_train[col].fillna(fill)
    df_test[col] = df_test[col].fillna(fill)

# IMPORTANT : reproduire les categories du modele V3 (sinon mismatch)
model_v3 = joblib.load(MODELS_DIR / "best_model_v3_osrm.pkl")
v3_cats = model_v3.booster_.pandas_categorical
cat_in_v3 = [c for c in FEATURES if c in cat_actual]
for col, cats in zip(cat_in_v3, v3_cats):
    df_train[col] = pd.Categorical(df_train[col].astype(int), categories=cats)
    df_test[col] = pd.Categorical(df_test[col].astype(int), categories=cats)

X_train_full = df_train[FEATURES].copy()
y_train_full = df_train["target"].copy()
X_test = df_test[FEATURES].copy()
y_test = df_test["target"].copy()

X_train, X_val, y_train, y_val = train_test_split(
    X_train_full, y_train_full, test_size=0.15, stratify=y_train_full, random_state=42)

print(f"Train core : {len(X_train):,} | Val : {len(X_val):,} | Test : {len(X_test):,}")
print()

# ==== Metriques train / val / test ====
print("=" * 60)
print("OVERFIT CHECK V3")
print("=" * 60)
for name, X, y in [("TRAIN", X_train, y_train), ("VAL", X_val, y_val), ("TEST", X_test, y_test)]:
    proba = model_v3.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    print(f"\n{name} ({len(y):,}) :")
    print(f"  recall_grave    : {recall_score(y, pred):.4f}")
    print(f"  precision_grave : {precision_score(y, pred):.4f}")
    print(f"  f1_macro        : {f1_score(y, pred, average='macro'):.4f}")
    print(f"  auc_roc         : {roc_auc_score(y, proba):.4f}")

# ==== Cross-validation 3-fold sur train_core ====
print(f"\n{'='*60}\nCV 3-fold sur train_core\n{'='*60}")
import lightgbm as lgb
# Memes params que V3 actuel
params = model_v3.get_params()
fresh_model = lgb.LGBMClassifier(**params)
cv_scores = cross_val_score(
    fresh_model, X_train, y_train,
    cv=StratifiedKFold(3, shuffle=True, random_state=42),
    scoring="recall", n_jobs=-1
)
print(f"  Recall CV : {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")
print(f"  Folds     : {[f'{s:.4f}' for s in cv_scores]}")
print(f"\n=> Si recall train > recall test + 5 points, suspecter overfit")
print(f"=> Si recall CV << recall test, suspecter underfit ou data leakage")

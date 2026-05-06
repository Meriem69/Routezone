"""
Training V3 final avec hyperparametres Optuna (sauvegardes par notebook 08).
Compare avec V3 vanilla pour mesurer la reduction de l'overfit.
"""
from pathlib import Path
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    recall_score, precision_score, f1_score, roc_auc_score, classification_report
)
from sklearn.calibration import CalibratedClassifierCV
import lightgbm as lgb

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"

print("Reconstruction du dataset V3 OSRM...")
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
    return [0,0,0,0,0,0,0,1,1,1,2,2,2,2,2,2,2,3,3,3,3,3,4,4][int(h)]

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

FEATURES = [
    "lum","agg","int_feat","atm","col","catr","circ","vosp","prof","plan","surf",
    "infra","situ","vma","catu","sexe","trajet","secu1","catv","age","heure","mois",
    "temperature","precipitation","windspeed",
    "creneau","age_tranche","jour_semaine","is_weekend",
    "vma_x_nuit","jeune_2roues","pluie_x_surface",
    "temps_total_osrm","zone_blanche_osrm",
]
FEATURES = [f for f in FEATURES if f in df.columns]
CATEGORICAL = ["lum","agg","atm","col","catr","circ","vosp","prof","plan","surf","infra","situ",
               "catu","sexe","trajet","secu1","catv","creneau","age_tranche","jour_semaine"]
if "int_feat" in FEATURES: CATEGORICAL.append("int_feat")
cat_actual = [c for c in CATEGORICAL if c in FEATURES]

mask_train = df["an"].isin([2022, 2023])
mask_test = df["an"] == 2024
df_train, df_test = df[mask_train].copy(), df[mask_test].copy()

# Imputation safe
for col in FEATURES:
    if col in cat_actual:
        fill = df_train[col].mode().iloc[0] if not df_train[col].mode().empty else 0
    else:
        fill = df_train[col].median() if df_train[col].notna().any() else 0
    df_train[col] = df_train[col].fillna(fill)
    df_test[col] = df_test[col].fillna(fill)

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
print()

# ---- Train avec hyperparametres Optuna ----
best = joblib.load(MODELS_DIR / "best_params_v3_osrm.pkl")
print(f"Hyperparametres Optuna : {best}")

params = {**best,
          "objective": "binary", "metric": "binary_logloss",
          "verbosity": -1, "boosting_type": "gbdt",
          "class_weight": "balanced", "random_state": 42}

print("\nEntrainement V3 final (Optuna)...")
model = lgb.LGBMClassifier(**params)
model.fit(X_train, y_train, categorical_feature=cat_actual)

# ---- Evaluation train / val / test ----
print("\n" + "=" * 70)
print("V3 OSRM Optuna - Performance par split")
print("=" * 70)
metrics = {}
for split, X, y in [("TRAIN", X_train, y_train), ("VAL", X_val, y_val), ("TEST", X_test, y_test)]:
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    m = {
        "recall": recall_score(y, pred),
        "precision": precision_score(y, pred),
        "f1_macro": f1_score(y, pred, average="macro"),
        "auc": roc_auc_score(y, proba),
    }
    metrics[split] = m
    print(f"\n{split:<6} ({len(y):>7,}):  "
          f"recall={m['recall']:.4f}  prec={m['precision']:.4f}  "
          f"f1={m['f1_macro']:.4f}  auc={m['auc']:.4f}")

# ---- Comparaison avec V3 vanilla et V2 ----
print("\n" + "=" * 70)
print("Comparaison V2 / V3 vanilla / V3 Optuna")
print("=" * 70)

# V3 vanilla : on a sauvegarde dans best_model_v3_osrm.pkl (avant Optuna)
# Ses metriques connues : test recall 0.7591, AUC 0.8554, gap train-test recall +9.7%

print(f"\n{'Metric':<14}{'V2 Hav':>10}{'V3 vanilla':>14}{'V3 Optuna':>14}{'V3 ovf':>10}")
print("-" * 70)
v2_metrics = {"recall": 0.7837, "precision": 0.4048, "f1_macro": 0.6885, "auc": 0.8553}
v3_vanilla = {"recall": 0.7591, "precision": 0.4181, "f1_macro": 0.6963, "auc": 0.8554, "train_recall": 0.8561}
gap_optuna = metrics["TRAIN"]["recall"] - metrics["TEST"]["recall"]
gap_vanilla = v3_vanilla["train_recall"] - v3_vanilla["recall"]

for k in ["recall", "precision", "f1_macro", "auc"]:
    print(f"{k:<14}{v2_metrics[k]:>10.4f}{v3_vanilla[k]:>14.4f}"
          f"{metrics['TEST'][k]:>14.4f}", end="")
    if k == "recall":
        print(f"{gap_optuna:>+10.4f}")
    else:
        print()

print(f"\nOverfit gap (recall train - recall test) :")
print(f"  V3 vanilla : {gap_vanilla:+.4f} (leger overfit)")
print(f"  V3 Optuna  : {gap_optuna:+.4f} ({'OK' if gap_optuna < 0.05 else 'leger overfit' if gap_optuna < 0.10 else 'OVERFIT'})")

# ---- Calibration + sauvegarde ----
print("\nCalibration isotonic sur validation reelle...")
calibrator = CalibratedClassifierCV(model, cv=3, method="isotonic")
calibrator.fit(X_val, y_val)

joblib.dump(model, MODELS_DIR / "best_model_v3_osrm.pkl")
joblib.dump(calibrator, MODELS_DIR / "calibrator_v3_osrm.pkl")
joblib.dump(FEATURES, MODELS_DIR / "features_v3_osrm.pkl")
print(f"Modele V3 final (Optuna) sauvegarde dans {MODELS_DIR}")

print("\n" + "=" * 70)
print("Classification report sur test 2024 :")
print(classification_report(y_test, (model.predict_proba(X_test)[:, 1] >= 0.5).astype(int),
                            target_names=["Pas grave", "Grave"]))

"""
Ablation study : mesure l'apport reel des features `temps_total_osrm` +
`zone_blanche_osrm` dans le modele V3.

Methodologie : memes hyperparametres Optuna, meme split, meme early stopping.
Seule difference : 3 jeux de features.

A) V3 OSRM full (34 features)         -> ref
B) V3 sans temps intervention (32)    -> isole l'apport COMPLET de la feature temps
C) V3 avec Haversine au lieu de OSRM  -> isole l'apport SPECIFIQUE d'OSRM vs Haversine
"""
from pathlib import Path
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import recall_score, precision_score, f1_score, roc_auc_score
import lightgbm as lgb

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"

print("Reconstruction du dataset...")
df = pd.read_csv(DATA_DIR / "dataset_clean.csv", low_memory=False)
df["target"] = df["grav"].map({1: 0, 4: 0, 2: 1, 3: 1})
df = df.dropna(subset=["target"])
df["target"] = df["target"].astype(int)

df_ti = pd.read_csv(DATA_DIR / "temps_intervention_osrm.csv").drop_duplicates("Num_Acc")
key = "Num_Acc" if "Num_Acc" in df.columns else "num_acc"
df = df.merge(df_ti, left_on=key, right_on="Num_Acc", how="left")
df["zone_blanche_osrm"] = (df["temps_total_osrm"] > 30).astype(int)
df["zone_blanche_hav"] = (df["temps_total_hav"] > 30).astype(int)


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

# Features de base (32) -- sans temps intervention
BASE_FEATURES = [
    "lum","agg","int_feat","atm","col","catr","circ","vosp","prof","plan","surf",
    "infra","situ","vma","catu","sexe","trajet","secu1","catv","age","heure","mois",
    "temperature","precipitation","windspeed",
    "creneau","age_tranche","jour_semaine","is_weekend",
    "vma_x_nuit","jeune_2roues","pluie_x_surface",
]
BASE_FEATURES = [f for f in BASE_FEATURES if f in df.columns]

CATEGORICAL_ALL = ["lum","agg","atm","col","catr","circ","vosp","prof","plan","surf","infra","situ",
                   "catu","sexe","trajet","secu1","catv","creneau","age_tranche","jour_semaine"]
if "int_feat" in df.columns: CATEGORICAL_ALL.append("int_feat")

# 3 configurations a tester
CONFIGS = {
    "A_OSRM (full)":     BASE_FEATURES + ["temps_total_osrm", "zone_blanche_osrm"],
    "B_AblationTotal":   BASE_FEATURES,
    "C_Haversine":       BASE_FEATURES + ["temps_total_hav", "zone_blanche_hav"],
}

# Hyperparametres V3 final (Optuna recall+ES)
best_params = joblib.load(MODELS_DIR / "best_params_v3_osrm.pkl")
print(f"Hyperparametres communs : {best_params}")

mask_train = df["an"].isin([2022, 2023])
mask_test = df["an"] == 2024
df_train = df[mask_train].copy()
df_test = df[mask_test].copy()

results = {}

for name, features in CONFIGS.items():
    print(f"\n{'='*70}")
    print(f"{name}  ({len(features)} features)")
    print(f"{'='*70}")

    cat_actual = [c for c in CATEGORICAL_ALL if c in features]

    # Imputation safe (re-faite par config car features differentes)
    dft = df_train.copy()
    dfe = df_test.copy()
    for col in features:
        if col in cat_actual:
            fill = dft[col].mode().iloc[0] if not dft[col].mode().empty else 0
        else:
            fill = dft[col].median() if dft[col].notna().any() else 0
        dft[col] = dft[col].fillna(fill)
        dfe[col] = dfe[col].fillna(fill)
    for col in cat_actual:
        dft[col] = dft[col].astype(int).astype("category")
        dfe[col] = dfe[col].astype(int).astype("category")

    X_full = dft[features].copy()
    y_full = dft["target"].copy()
    X_test_ = dfe[features].copy()
    y_test_ = dfe["target"].copy()
    X_tr, X_val, y_tr, y_val = train_test_split(X_full, y_full, test_size=0.15, stratify=y_full, random_state=42)

    params = {**best_params,
              "objective": "binary", "metric": "binary_logloss",
              "verbosity": -1, "boosting_type": "gbdt",
              "n_estimators": 1000,
              "class_weight": "balanced", "random_state": 42}

    model = lgb.LGBMClassifier(**params)
    model.fit(X_tr, y_tr,
              eval_set=[(X_val, y_val)],
              categorical_feature=cat_actual,
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
    print(f"Best iteration : {model.best_iteration_}")

    # Metriques par split
    metrics = {}
    for split_name, X_, y_ in [("train", X_tr, y_tr), ("val", X_val, y_val), ("test", X_test_, y_test_)]:
        proba = model.predict_proba(X_)[:, 1]
        pred = (proba >= 0.5).astype(int)
        metrics[split_name] = {
            "recall": recall_score(y_, pred),
            "precision": precision_score(y_, pred),
            "f1_macro": f1_score(y_, pred, average="macro"),
            "auc": roc_auc_score(y_, proba),
        }
    results[name] = metrics

    print(f"\n{'split':<8}{'recall':>10}{'prec':>10}{'f1_macro':>12}{'auc':>10}")
    for split, m in metrics.items():
        print(f"{split:<8}{m['recall']:>10.4f}{m['precision']:>10.4f}{m['f1_macro']:>12.4f}{m['auc']:>10.4f}")
    gap = metrics["train"]["recall"] - metrics["test"]["recall"]
    print(f"Gap train-test recall : {gap:+.4f}")


# Tableau comparatif final
print("\n" + "=" * 80)
print("ABLATION FINALE -- Test 2024")
print("=" * 80)
print(f"\n{'Config':<22}{'recall':>10}{'precision':>12}{'f1_macro':>12}{'auc':>10}{'gap':>10}")
print("-" * 80)
for name, m in results.items():
    test = m["test"]
    gap = m["train"]["recall"] - m["test"]["recall"]
    print(f"{name:<22}{test['recall']:>10.4f}{test['precision']:>12.4f}{test['f1_macro']:>12.4f}{test['auc']:>10.4f}{gap:>+10.4f}")

# Deltas vs A (full OSRM)
ref = results["A_OSRM (full)"]["test"]
print(f"\n{'Config':<22}{'d_recall':>12}{'d_precision':>14}{'d_f1':>10}{'d_auc':>10}")
print("-" * 80)
for name in ["B_AblationTotal", "C_Haversine"]:
    t = results[name]["test"]
    print(f"{name:<22}"
          f"{t['recall']-ref['recall']:>+12.4f}"
          f"{t['precision']-ref['precision']:>+14.4f}"
          f"{t['f1_macro']-ref['f1_macro']:>+10.4f}"
          f"{t['auc']-ref['auc']:>+10.4f}")

print(f"\nApport feature temps OSRM (A vs B)  :")
print(f"  recall    : {(ref['recall']-results['B_AblationTotal']['test']['recall'])*100:+.2f} pts")
print(f"  AUC       : {(ref['auc']-results['B_AblationTotal']['test']['auc'])*100:+.2f} pts")
print(f"  F1 macro  : {(ref['f1_macro']-results['B_AblationTotal']['test']['f1_macro'])*100:+.2f} pts")
print(f"\nApport SPECIFIQUE OSRM vs Haversine (A vs C)  :")
print(f"  recall    : {(ref['recall']-results['C_Haversine']['test']['recall'])*100:+.2f} pts")
print(f"  AUC       : {(ref['auc']-results['C_Haversine']['test']['auc'])*100:+.2f} pts")
print(f"  F1 macro  : {(ref['f1_macro']-results['C_Haversine']['test']['f1_macro'])*100:+.2f} pts")

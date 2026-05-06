"""
Optuna V3 OSRM v2 : optimise pour RECALL (et plus AUC), avec early stopping
sur la validation set pour reduire l'overfit.

Compare 3 modeles :
- V3 vanilla (n_estimators=500 fixe, defaults)
- V3 Optuna AUC (run precedent : overfit +14.5%)
- V3 Optuna RECALL+ES (ce script)
"""
from pathlib import Path
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import recall_score, precision_score, f1_score, roc_auc_score, classification_report
from sklearn.calibration import CalibratedClassifierCV
import lightgbm as lgb
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

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
print(f"{len(FEATURES)} features V3\n")


def objective(trial):
    """Optimise recall sur validation reelle, avec early stopping."""
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "verbosity": -1,
        "boosting_type": "gbdt",
        "n_estimators": 1000,  # haut, on laisse early stopping decider
        "max_depth": trial.suggest_int("max_depth", 4, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 20, 80),
        "min_child_samples": trial.suggest_int("min_child_samples", 50, 300),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 1.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 1.0, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 0.95),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 0.9),
        "class_weight": "balanced",
        "random_state": 42,
    }
    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        categorical_feature=cat_actual,
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    proba = model.predict_proba(X_val)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return recall_score(y_val, pred)


print("Optuna 30 trials (recall_val + early stopping)...")
study = optuna.create_study(direction="maximize", study_name="v3_osrm_recall_es")
study.optimize(objective, n_trials=30, n_jobs=1, show_progress_bar=False)

print(f"\nBest recall (validation) : {study.best_value:.4f}")
print(f"Best params : {study.best_params}")

# Train final
final_params = {**study.best_params,
                "objective": "binary", "metric": "binary_logloss",
                "verbosity": -1, "boosting_type": "gbdt", "n_estimators": 1000,
                "class_weight": "balanced", "random_state": 42}

print("\nEntrainement final avec early stopping...")
model = lgb.LGBMClassifier(**final_params)
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    categorical_feature=cat_actual,
    callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
)
print(f"Best iteration : {model.best_iteration_}")

print("\n" + "=" * 70)
print("V3 OSRM Optuna+ES (recall optim) - Performance par split")
print("=" * 70)
results = {}
for split, X, y in [("TRAIN", X_train, y_train), ("VAL", X_val, y_val), ("TEST", X_test, y_test)]:
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    m = {
        "recall": recall_score(y, pred),
        "precision": precision_score(y, pred),
        "f1_macro": f1_score(y, pred, average="macro"),
        "auc": roc_auc_score(y, proba),
    }
    results[split] = m
    print(f"{split:<6} ({len(y):>7,}):  recall={m['recall']:.4f}  prec={m['precision']:.4f}  f1={m['f1_macro']:.4f}  auc={m['auc']:.4f}")

gap = results["TRAIN"]["recall"] - results["TEST"]["recall"]
print(f"\nOverfit gap (recall train-test) : {gap:+.4f}  -> {'OK' if gap < 0.05 else 'leger overfit' if gap < 0.10 else 'OVERFIT'}")

# Comparaison finale
print("\n" + "=" * 80)
print("COMPARAISON FINALE")
print("=" * 80)
print(f"\n{'Metric':<14}{'V2 Hav':>10}{'V3 van':>10}{'V3 Opt-AUC':>14}{'V3 Opt-Rec+ES':>16}")
print("-" * 80)
v2 = {"recall": 0.7837, "precision": 0.4048, "f1_macro": 0.6885, "auc": 0.8553}
v3v = {"recall": 0.7591, "precision": 0.4181, "f1_macro": 0.6963, "auc": 0.8554}
v3a = {"recall": 0.7397, "precision": 0.4279, "f1_macro": 0.7011, "auc": 0.8544}
for k in ["recall", "precision", "f1_macro", "auc"]:
    print(f"{k:<14}{v2[k]:>10.4f}{v3v[k]:>10.4f}{v3a[k]:>14.4f}{results['TEST'][k]:>16.4f}")
print("-" * 80)
print(f"{'gap recall':<14}{'-':>10}{'+0.0970':>10}{'+0.1452':>14}{gap:>+16.4f}")

# Sauvegarde V3 Optuna+ES (la meilleure pour Golden Hour si recall meilleur)
calibrator = CalibratedClassifierCV(model, cv=3, method="isotonic")
calibrator.fit(X_val, y_val)
joblib.dump(model, MODELS_DIR / "best_model_v3_osrm.pkl")
joblib.dump(calibrator, MODELS_DIR / "calibrator_v3_osrm.pkl")
joblib.dump(FEATURES, MODELS_DIR / "features_v3_osrm.pkl")
joblib.dump(study.best_params, MODELS_DIR / "best_params_v3_osrm.pkl")
print(f"\nModele V3 final sauvegarde dans {MODELS_DIR}")
print("\nClassification report test 2024 :")
print(classification_report(y_test, (model.predict_proba(X_test)[:,1] >= 0.5).astype(int),
                            target_names=["Pas grave","Grave"]))

import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
import os

# Chemins
DATA_DIR = Path(__file__).parent.parent / 'data' / 'processed'
CSV_PATH = DATA_DIR / 'dataset_clean.csv'
METEO_CSV = DATA_DIR / 'dataset_enriched.csv'
BAROMETRE_CSV = DATA_DIR / 'barometre_onisr.csv'
TEMPS_CSV = DATA_DIR / 'temps_intervention_osrm.csv'
SQL_PATH = Path(__file__).parent / 'create_db.sql'

# Connexion PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://routezone:routezone_pwd_2024@127.0.0.1:5432/routezone"
)

print(f"CSV : {CSV_PATH}")
print(f"BDD : {DATABASE_URL.split('@')[1]}")  # masque le mot de passe

# Chargement du CSV
print("Chargement du dataset...")
df = pd.read_csv(CSV_PATH, low_memory=False)
print(f"{len(df):,} lignes chargées | {df.shape[1]} colonnes")
print(df.columns.tolist())

# Nettoyage 'dep' : pandas a cast en float -> "69.0", on remet en TEXT propre.
# .replace(...) gere les eventuels NaN convertis en string "nan".
# Robuste si Corse "2A"/"2B" presente : pas de .0 a stripper, valeur preservee.
df['dep'] = (
    df['dep'].astype(str)
    .str.replace(r'\.0$', '', regex=True)
    .replace({'nan': None, 'NaN': None, '<NA>': None})
)

# Connexion à la BDD
print("\nConnexion à PostgreSQL...")
engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    print("Connecté !")

    # Création du schéma
    print("\nCréation du schéma...")
    with open(SQL_PATH, 'r') as f:
        for statement in f.read().split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
    print("Schéma créé !")

    # Idempotence : vide les tables data avant ré-import (CASCADE pour les FK)
    print("\nNettoyage des tables (idempotence)...")
    conn.execute(text(
        "TRUNCATE TABLE accidents, lieux, vehicules, usagers, "
        "meteo, barometre_onisr, temps_intervention "
        "RESTART IDENTITY CASCADE"
    ))
    print("Tables vidées (users et predictions préservées).")

# PREPARATION DES DONNEES PR CHAQUE TABLE :

# Préparation table accidents
print("\nPréparation table accidents...")
accidents = df[[
    'Num_Acc', 'jour', 'mois', 'an',
    'heure', 'lum', 'agg',
    'int', 'atm', 'col', 'lat', 'long', 'dep'
]].drop_duplicates(subset=['Num_Acc']).copy()

accidents = accidents.rename(columns={'int': 'intersec', 'Num_Acc': 'num_acc'})
print(f"{len(accidents):,} accidents")

# Préparation table lieux
print("\nPréparation table lieux...")
lieux = df[[
    'Num_Acc', 'catr', 'circ', 'nbv', 'vosp',
    'prof', 'plan', 'larrout', 'surf', 'infra', 'situ', 'vma'
]].drop_duplicates(subset=['Num_Acc']).copy()

lieux = lieux.rename(columns={'Num_Acc': 'num_acc'})
# larrout : virgule française "6,4" et "-1" stringy → float (NaN si invalide)
lieux['larrout'] = (
    lieux['larrout'].astype(str).str.strip().str.replace(',', '.', regex=False)
)
lieux['larrout'] = pd.to_numeric(lieux['larrout'], errors='coerce')
print(f"{len(lieux):,} lieux")

# Préparation table vehicules
print("\nPréparation table vehicules...")
vehicules = df[[
    'id_vehicule', 'Num_Acc', 'senc', 'catv', 'obs', 'obsm', 'choc', 'manv', 'motor'
]].drop_duplicates(subset=['id_vehicule']).copy()

vehicules = vehicules.rename(columns={'Num_Acc': 'num_acc'})
# id_vehicule : NBSP (U+00A0) comme separateur de milliers dans BAAC → int
vehicules['id_vehicule'] = (
    vehicules['id_vehicule'].astype(str)
    .str.replace('\xa0', '', regex=False)
    .str.replace(' ', '', regex=False)
)
vehicules['id_vehicule'] = pd.to_numeric(vehicules['id_vehicule'], errors='coerce').astype('Int64')
vehicules = vehicules.dropna(subset=['id_vehicule']).copy()
print(f"{len(vehicules):,} vehicules")

# Préparation table usagers
print("\nPréparation table usagers...")
usagers = df[[
    'id_usager', 'Num_Acc', 'id_vehicule', 'place', 'catu', 'grav', 'sexe', 'an_nais', 'trajet', 'secu1'
]].drop_duplicates(subset=['id_usager']).copy()

usagers = usagers.rename(columns={'Num_Acc': 'num_acc'})
# id_usager + id_vehicule : meme cleanup NBSP / espace
for col in ('id_usager', 'id_vehicule'):
    usagers[col] = (
        usagers[col].astype(str)
        .str.replace('\xa0', '', regex=False)
        .str.replace(' ', '', regex=False)
    )
    usagers[col] = pd.to_numeric(usagers[col], errors='coerce').astype('Int64')
usagers = usagers.dropna(subset=['id_usager']).copy()
print(f"{len(usagers):,} usagers")

# Import dans la BDD
print("\nImport en cours...")
accidents.to_sql('accidents', engine, if_exists='append', index=False, method='multi', chunksize=5000)
print("accidents ok")
lieux.to_sql('lieux', engine, if_exists='append', index=False, method='multi', chunksize=5000)
print("lieux ok")
vehicules.to_sql('vehicules', engine, if_exists='append', index=False, method='multi', chunksize=5000)
print("vehicules ok")
usagers.to_sql('usagers', engine, if_exists='append', index=False, method='multi', chunksize=5000)
print("usagers ok")

# === Table meteo (depuis dataset_enriched.csv) ===
if METEO_CSV.exists():
    print("\nPréparation table meteo...")
    df_meteo = pd.read_csv(
        METEO_CSV,
        low_memory=False,
        usecols=['Num_Acc', 'temperature', 'precipitation', 'windspeed', 'weathercode'],
    )
    df_meteo = df_meteo.drop_duplicates(subset=['Num_Acc']).copy()
    df_meteo = df_meteo.rename(columns={'Num_Acc': 'num_acc'})
    # garde les lignes avec au moins une valeur météo (sinon ~10% utilisable)
    df_meteo = df_meteo.dropna(
        subset=['temperature', 'precipitation', 'windspeed', 'weathercode'],
        how='all',
    )
    # weathercode INTEGER nullable
    df_meteo['weathercode'] = df_meteo['weathercode'].astype('Int64')
    print(f"{len(df_meteo):,} lignes meteo (avec >=1 valeur non-null)")
    df_meteo.to_sql('meteo', engine, if_exists='append', index=False, method='multi', chunksize=5000)
    print("meteo ok")
else:
    print(f"\n[SKIP] meteo : {METEO_CSV} introuvable")

# === Table barometre_onisr (depuis barometre_onisr.csv) ===
if BAROMETRE_CSV.exists():
    print("\nPréparation table barometre_onisr...")
    # encoding='utf-8-sig' pour stripper le BOM sur la 1re colonne
    df_baro = pd.read_csv(BAROMETRE_CSV, encoding='utf-8-sig')
    if 'tues_metropole' in df_baro.columns:
        df_baro['tues_metropole'] = df_baro['tues_metropole'].astype('Int64')
    print(f"{len(df_baro):,} lignes barometre_onisr")
    df_baro.to_sql('barometre_onisr', engine, if_exists='append', index=False, method='multi', chunksize=5000)
    print("barometre_onisr ok")
else:
    print(f"\n[SKIP] barometre_onisr : {BAROMETRE_CSV} introuvable")

# === Table temps_intervention (depuis temps_intervention_osrm.csv) ===
if TEMPS_CSV.exists():
    print("\nPréparation table temps_intervention...")
    df_temps = pd.read_csv(TEMPS_CSV)
    df_temps = df_temps[[
        'Num_Acc',
        'nearest_pompiers_min_osrm',
        'nearest_sau_min_osrm',
        'temps_total_osrm',
    ]].copy()
    df_temps = df_temps.rename(columns={
        'Num_Acc': 'num_acc',
        'nearest_pompiers_min_osrm': 'nearest_pompiers_min',
        'nearest_sau_min_osrm': 'nearest_sau_min',
        'temps_total_osrm': 'temps_intervention_min',
    })
    # colonnes _nom et _km du schéma absentes du CSV → NULL
    df_temps['nearest_sau_nom'] = None
    df_temps['nearest_sau_km'] = None
    df_temps['nearest_pompiers_nom'] = None
    df_temps['nearest_pompiers_km'] = None
    df_temps = df_temps.drop_duplicates(subset=['num_acc']).copy()
    print(f"{len(df_temps):,} lignes temps_intervention")
    df_temps.to_sql('temps_intervention', engine, if_exists='append', index=False, method='multi', chunksize=5000)
    print("temps_intervention ok")
else:
    print(f"\n[SKIP] temps_intervention : {TEMPS_CSV} introuvable")

print("\nImport terminé !")

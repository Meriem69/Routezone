import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
import os

# Chemins
CSV_PATH = Path(__file__).parent.parent / 'data' / 'processed' / 'dataset_clean.csv'
SQL_PATH = Path(__file__).parent / 'create_db.sql'

# Connexion PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://routezone:routezone_pwd_2024@localhost:5432/routezone"
)

print(f"CSV : {CSV_PATH}")
print(f"BDD : {DATABASE_URL.split('@')[1]}")  # masque le mot de passe

# Chargement du CSV
print("Chargement du dataset...")
df = pd.read_csv(CSV_PATH, low_memory=False)
print(f"{len(df):,} lignes chargées | {df.shape[1]} colonnes")
print(df.columns.tolist())

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
print(f"{len(lieux):,} lieux")

# Préparation table vehicules
print("\nPréparation table vehicules...")
vehicules = df[[
    'id_vehicule', 'Num_Acc', 'senc', 'catv', 'obs', 'obsm', 'choc', 'manv', 'motor'
]].drop_duplicates(subset=['id_vehicule']).copy()

vehicules = vehicules.rename(columns={'Num_Acc': 'num_acc'})
print(f"{len(vehicules):,} vehicules")

# Préparation table usagers
print("\nPréparation table usagers...")
usagers = df[[
    'id_usager', 'Num_Acc', 'id_vehicule', 'place', 'catu', 'grav', 'sexe', 'an_nais', 'trajet', 'secu1'
]].drop_duplicates(subset=['id_usager']).copy()

usagers = usagers.rename(columns={'Num_Acc': 'num_acc'})
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

print("\nImport terminé !")

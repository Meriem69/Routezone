import sqlite3
import pandas as pd
from pathlib import Path

# Chemins
DB_PATH = Path(__file__).parent / 'routezone.db'
CSV_PATH = Path(__file__).parent.parent / 'data' / 'processed' / 'dataset_clean.csv'

print(f"BDD : {DB_PATH}")
print(f"CSV : {CSV_PATH}")

# Chargement du CSV
print("Chargement du dataset...")
df = pd.read_csv(CSV_PATH, low_memory=False)
print(f"{len(df):,} lignes chargées | {df.shape[1]} colonnes")
print(df.columns.tolist())

# Connexion à la BDD
print("\nConnexion à la BDD...")
conn = sqlite3.connect(DB_PATH)
print("Connecté !")

#PREPARATION DES DONNEES PR CHAQUE TABLE :

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
accidents.to_sql('accidents', conn, if_exists='replace', index=False)
print("accidents ok")
lieux.to_sql('lieux', conn, if_exists='replace', index=False)
print("lieux ok")
vehicules.to_sql('vehicules', conn, if_exists='replace', index=False)
print("vehicules ok")
usagers.to_sql('usagers', conn, if_exists='replace', index=False)
print("usagers ok")

# Fermeture connexion
conn.close()
print("\nImport terminé ! BDD fermée.")
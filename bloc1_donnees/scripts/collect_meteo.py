import sqlite3        # pour se connecter à la BDD SQLite
import requests       # pour faire des requêtes HTTP vers l'API Open-Meteo
import pandas as pd   # pour manipuler les données
from pathlib import Path  # pour gérer les chemins de fichiers
from time import sleep    # pour faire des pauses entre les requêtes API
from datetime import datetime  # pour manipuler les dates

# ── Chemins ──────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / 'bdd' / 'routezone.db'

# ── Connexion à la BDD ───────────────────────────────────────
conn = sqlite3.connect(DB_PATH)

# On récupère les accidents qui ont des coordonnées GPS valides
# et qui ne sont pas encore dans la table météo
query = """
    SELECT a.num_acc, a.lat, a.long, a.jour, a.mois, a.an, a.heure
    FROM accidents a
    LEFT JOIN meteo m ON a.num_acc = m.num_acc
    WHERE a.lat IS NOT NULL 
    AND a.long IS NOT NULL
    AND m.num_acc IS NULL
    LIMIT 500
"""
# LIMIT 500 → on teste sur 500 accidents d'abord
# si tout marche on pourra enlever la limite plus tard

df = pd.read_sql_query(query, conn)
print(f"{len(df):,} accidents à enrichir")

# ── Fonction qui appelle l'API Open-Meteo ────────────────────
def get_meteo(lat, lon, date_str, heure):
    """
    Appelle l'API Open-Meteo pour récupérer la météo historique
    à un endroit et un moment précis.
    
    lat, lon   : coordonnées GPS de l'accident
    date_str   : date au format 'YYYY-MM-DD'
    heure      : heure de l'accident (0-23)
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "Europe/Paris"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        # timeout=10 → si l'API répond pas en 10 secondes on abandonne
        
        if response.status_code == 200:
            data = response.json()
            hourly = data['hourly']
            
            # On récupère les données à l'heure exacte de l'accident
            idx = int(heure) if pd.notna(heure) else 12
            # si l'heure est manquante on prend midi par défaut
            
            return {
                'temperature': hourly['temperature_2m'][idx],
                'precipitation': hourly['precipitation'][idx],
                'windspeed': hourly['windspeed_10m'][idx],
                'weathercode': hourly['weathercode'][idx]
            }
    except Exception as e:
        # Si erreur (réseau, API down...) on retourne None
        print(f"Erreur API : {e}")
        return None

# ── Boucle principale ────────────────────────────────────────
print("Démarrage de la collecte météo...")
resultats = []  # liste qui va stocker les résultats

for i, row in df.iterrows():
    # On formate la date au format attendu par l'API : 'YYYY-MM-DD'
    date_str = f"{int(row['an'])}-{int(row['mois']):02d}-{int(row['jour']):02d}"
    # :02d → formate avec 2 chiffres ex: 3 → '03'
    
    meteo = get_meteo(row['lat'], row['long'], date_str, row['heure'])
    
    if meteo:
        meteo['num_acc'] = row['num_acc']
        meteo['source_api'] = 'open-meteo'
        meteo['date_collecte'] = datetime.today().strftime('%Y-%m-%d')
        resultats.append(meteo)
    
    # Pause de 0.1 seconde entre chaque requête
    # pour ne pas surcharger l'API et éviter d'être bloqué
    sleep(0.1)
    
    # Affiche la progression toutes les 50 requêtes
    if (i + 1) % 50 == 0:
        print(f"  {i + 1}/{len(df)} traités...")

# ── Import dans la BDD ───────────────────────────────────────
if resultats:
    df_meteo = pd.DataFrame(resultats)
    df_meteo.to_sql('meteo', conn, if_exists='append', index=False)
    # if_exists='append' → on ajoute aux données existantes
    # (pas 'replace' comme avant — on veut pas effacer ce qu'on a déjà)
    print(f"\n✓ {len(df_meteo):,} lignes météo importées dans la BDD")
else:
    print("Aucun résultat à importer")

# ── Fermeture ────────────────────────────────────────────────
conn.close()
print("Terminé !")
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import re
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / 'bdd' / 'routezone.db'
OUTPUT = Path(__file__).parent.parent / 'data' / 'processed' / 'barometre_onisr.csv'

# ── URL à scraper ─────────────────────────────────────────────
URL = "https://www.onisr.securite-routiere.gouv.fr/etat-de-l-insecurite-routiere?field_theme_target_id=645"

# ── Headers — on se fait passer pour un navigateur ───────────
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ── Requête HTTP ──────────────────────────────────────────────
print("Connexion au site ONISR...")
response = requests.get(URL, headers=headers, timeout=15)
print(f"Statut : {response.status_code}")

# ── Parsing HTML ──────────────────────────────────────────────
soup = BeautifulSoup(response.text, 'html.parser')
articles = soup.find_all('article', class_='article-card')
print(f"{len(articles)} articles trouvés")

resultats = []

for article in articles:
    try:
        # Titre — dans la balise h2
        titre = article.find('h2', class_='article-card_title')
        titre = titre.get_text(strip=True) if titre else None

        # Date — dans la balise time
        date = article.find('time')
        date = date.get_text(strip=True) if date else None

        # Résumé — dans article-card_content
        resume = article.find('div', class_='article-card_content')
        resume = resume.get_text(strip=True) if resume else None

        # Extraction du nombre de tués depuis le résumé
        # ex: "202 personnes sont décédées" → 202
        tues = None
        if resume:
            match = re.search(r'(\d+)\s+personnes?\s+sont\s+décédées?', resume)
            if match:
                tues = int(match.group(1))

        if titre:
            resultats.append({
                'titre': titre,
                'date_publication': date,
                'tues_metropole': tues,
                'resume': resume,
                'source': 'ONISR barometre mensuel',
                'url': URL
            })

    except Exception as e:
        print(f"Erreur : {e}")
        continue

print(f"\n{len(resultats)} baromètres extraits")

# ── Sauvegarde CSV ────────────────────────────────────────────
df = pd.DataFrame(resultats)
print(df.head())
df.to_csv(OUTPUT, index=False, encoding='utf-8-sig')
print(f"\n✓ CSV sauvegardé → {OUTPUT}")

# ── Sauvegarde BDD ────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
df.to_sql('barometre_onisr', conn, if_exists='replace', index=False)
print("✓ Importé dans la BDD → table barometre_onisr")
conn.close()
print("\nTerminé !")
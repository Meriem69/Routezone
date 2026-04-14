"""
RouteZone — API données
=======================
FastAPI qui expose les données d'accidents BAAC via des endpoints HTTP.
Compétence C5 — Bloc 1 — Certification RNCP37827 Dev IA Simplon

Lancer l'API :
    uvicorn main:app --reload

Accéder à la documentation automatique :
    http://localhost:8000/docs
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional

# ── Initialisation de l'application ──────────────────────────────
app = FastAPI(
    title="RouteZone API — Données accidents BAAC",
    description="""
API REST qui expose les données d'accidents routiers BAAC 2022-2024.
Construite avec FastAPI dans le cadre du projet RouteZone (certification RNCP37827).

**Sources de données :**
- BAAC (Bulletin d'Analyse des Accidents Corporels) 2022-2024
- API Open-Meteo (enrichissement météo)
- ONISR (baromètre mensuel scraping)
    """,
    version="1.0.0"
)

# ── CORS — permet à n'importe quelle app d'appeler cette API ─────
# En production on restreindrait aux domaines autorisés
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Chemin vers la BDD SQLite ─────────────────────────────────────
# __file__ = chemin du main.py
# on remonte 2 niveaux pour arriver à la racine du projet
DB_PATH = Path(__file__).parent.parent / "bdd" / "routezone.db"


def get_connection():
    """
    Ouvre une connexion à la BDD SQLite.
    row_factory = sqlite3.Row permet de récupérer les résultats
    sous forme de dictionnaires plutôt que de tuples.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # résultats sous forme de dict
    return conn


# ── Route racine ──────────────────────────────────────────────────
@app.get("/")
def accueil():
    """
    Route d'accueil — vérifie que l'API est bien en ligne.
    """
    return {
        "message": "RouteZone API — Données accidents BAAC 2022-2024",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": [
            "/accidents",
            "/accidents/stats",
            "/accidents/departement/{dep}",
            "/accidents/gravite",
            "/meteo/stats",
            "/onisr/barometre"
        ]
    }


# ── Route 1 : liste des accidents avec filtres ────────────────────
@app.get("/accidents")
def liste_accidents(
    departement: Optional[str] = Query(None, description="Numéro de département (ex: 69)"),
    annee: Optional[int] = Query(None, description="Année (2022, 2023 ou 2024)"),
    gravite: Optional[int] = Query(None, description="Gravité : 1=Indemne, 2=Tué, 3=Hospitalisé, 4=Blessé léger"),
    limite: int = Query(100, description="Nombre de résultats maximum (défaut: 100, max: 1000)")
):
    """
    Retourne la liste des accidents avec filtres optionnels.

    - **departement** : filtre par département (ex: 69 pour le Rhône)
    - **annee** : filtre par année (2022, 2023 ou 2024)
    - **gravite** : filtre par niveau de gravité
    - **limite** : nombre max de résultats (max 1000)
    """
    # Sécurité : on limite à 1000 résultats max pour éviter les surcharges
    if limite > 1000:
        limite = 1000

    # Construction de la requête SQL dynamiquement selon les filtres
    query = "SELECT * FROM accidents WHERE 1=1"
    params = []

    if departement:
        query += " AND dep = ?"
        params.append(departement)

    if annee:
        query += " AND an = ?"
        params.append(annee)

    if gravite:
        # grav est dans la table usagers, pas accidents
        # on fait une sous-requête pour filtrer
        query = f"""
            SELECT DISTINCT a.*
            FROM accidents a
            JOIN usagers u ON a.num_acc = u.num_acc
            WHERE u.grav = ?
        """
        params = [gravite]
        if departement:
            query += " AND a.dep = ?"
            params.append(departement)
        if annee:
            query += " AND a.an = ?"
            params.append(annee)

    query += f" LIMIT {limite}"

    try:
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return {
            "total": len(df),
            "filtres": {
                "departement": departement,
                "annee": annee,
                "gravite": gravite
            },
            "accidents": df.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── Route 2 : statistiques globales ──────────────────────────────
@app.get("/accidents/stats")
def statistiques_globales():
    """
    Retourne des statistiques globales sur le dataset.

    - Nombre total d'accidents
    - Répartition par année
    - Répartition par gravité
    - Départements les plus accidentogènes
    """
    try:
        conn = get_connection()

        # Total accidents
        total = pd.read_sql_query("SELECT COUNT(*) as total FROM accidents", conn)

        # Par année
        par_annee = pd.read_sql_query(
            "SELECT an, COUNT(*) as nb_accidents FROM accidents GROUP BY an ORDER BY an",
            conn
        )

        # Par gravité (depuis la table usagers)
        par_gravite = pd.read_sql_query(
            """SELECT grav,
                      COUNT(*) as nb_usagers,
                      CASE grav
                          WHEN 1 THEN 'Indemne'
                          WHEN 2 THEN 'Tué'
                          WHEN 3 THEN 'Hospitalisé'
                          WHEN 4 THEN 'Blessé léger'
                          ELSE 'Inconnu'
                      END as libelle
               FROM usagers
               GROUP BY grav
               ORDER BY grav""",
            conn
        )

        # Top 10 départements
        top_dep = pd.read_sql_query(
            """SELECT dep, COUNT(*) as nb_accidents
               FROM accidents
               GROUP BY dep
               ORDER BY nb_accidents DESC
               LIMIT 10""",
            conn
        )

        conn.close()

        return {
            "total_accidents": int(total["total"].iloc[0]),
            "par_annee": par_annee.to_dict(orient="records"),
            "par_gravite": par_gravite.to_dict(orient="records"),
            "top_10_departements": top_dep.to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── Route 3 : accidents par département ──────────────────────────
@app.get("/accidents/departement/{dep}")
def accidents_par_departement(
    dep: str,
    annee: Optional[int] = Query(None, description="Filtrer par année")
):
    """
    Retourne les statistiques d'accidents pour un département précis.

    - **dep** : numéro de département (ex: 69, 13, 75)
    """
    query = """
        SELECT
            a.an,
            a.mois,
            COUNT(DISTINCT a.num_acc) as nb_accidents,
            SUM(CASE WHEN u.grav = 2 THEN 1 ELSE 0 END) as nb_tues,
            SUM(CASE WHEN u.grav = 3 THEN 1 ELSE 0 END) as nb_hospitalises,
            SUM(CASE WHEN u.grav = 4 THEN 1 ELSE 0 END) as nb_blesses_legers
        FROM accidents a
        LEFT JOIN usagers u ON a.num_acc = u.num_acc
        WHERE a.dep = ?
    """
    params = [dep]

    if annee:
        query += " AND a.an = ?"
        params.append(annee)

    query += " GROUP BY a.an, a.mois ORDER BY a.an, a.mois"

    try:
        conn = get_connection()

        # Vérifier que le département existe
        check = pd.read_sql_query(
            "SELECT COUNT(*) as nb FROM accidents WHERE dep = ?", conn, params=[dep]
        )
        if check["nb"].iloc[0] == 0:
            conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"Département {dep} non trouvé dans la base de données"
            )

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        return {
            "departement": dep,
            "annee_filtre": annee,
            "total_accidents": int(df["nb_accidents"].sum()),
            "total_tues": int(df["nb_tues"].sum()),
            "stats_par_mois": df.to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── Route 4 : répartition par gravité ────────────────────────────
@app.get("/accidents/gravite")
def repartition_gravite(
    annee: Optional[int] = Query(None, description="Filtrer par année"),
    departement: Optional[str] = Query(None, description="Filtrer par département")
):
    """
    Retourne la répartition des accidents par niveau de gravité.
    """
    query = """
        SELECT
            u.grav,
            CASE u.grav
                WHEN 1 THEN 'Indemne'
                WHEN 2 THEN 'Tué'
                WHEN 3 THEN 'Hospitalisé'
                WHEN 4 THEN 'Blessé léger'
            END as libelle,
            COUNT(*) as nb_usagers
        FROM usagers u
        JOIN accidents a ON u.num_acc = a.num_acc
        WHERE u.grav IS NOT NULL
    """
    params = []

    if annee:
        query += " AND a.an = ?"
        params.append(annee)

    if departement:
        query += " AND a.dep = ?"
        params.append(departement)

    query += " GROUP BY u.grav ORDER BY u.grav"

    try:
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        total = df["nb_usagers"].sum()
        df["pourcentage"] = (df["nb_usagers"] / total * 100).round(1)

        return {
            "filtres": {"annee": annee, "departement": departement},
            "total_usagers": int(total),
            "repartition": df.to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── Route 5 : stats météo API ─────────────────────────────────────
@app.get("/meteo/stats")
def stats_meteo():
    """
    Retourne des statistiques sur les données météo collectées via l'API Open-Meteo.
    """
    try:
        conn = get_connection()

        # Vérifier si la table meteo existe
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meteo'", conn
        )
        if tables.empty:
            conn.close()
            return {"message": "Table meteo non disponible — relancer le notebook_02_api_meteo"}

        stats = pd.read_sql_query(
            """SELECT
                COUNT(*) as nb_accidents_enrichis,
                ROUND(AVG(temperature), 1) as temp_moyenne,
                ROUND(MIN(temperature), 1) as temp_min,
                ROUND(MAX(temperature), 1) as temp_max,
                ROUND(AVG(precipitation), 2) as pluie_moyenne,
                ROUND(AVG(windspeed), 1) as vent_moyen
               FROM meteo""",
            conn
        )
        conn.close()

        return {
            "source": "API Open-Meteo (météo historique)",
            "stats": stats.to_dict(orient="records")[0]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── Route 6 : baromètre ONISR ────────────────────────────────────
@app.get("/onisr/barometre")
def barometre_onisr(
    annee: Optional[int] = Query(None, description="Filtrer par année (2022, 2023, 2024)")
):
    """
    Retourne les données du baromètre mensuel ONISR scrapées depuis le site officiel.
    """
    try:
        conn = get_connection()

        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='barometre_onisr'", conn
        )
        if tables.empty:
            conn.close()
            return {"message": "Table barometre_onisr non disponible — relancer le notebook_03"}

        query = "SELECT titre, annee, mois, tues_metropole, date_publication FROM barometre_onisr"
        params = []

        if annee:
            query += " WHERE annee = ?"
            params.append(annee)

        query += " ORDER BY annee, mois"

        df = pd.read_sql_query(query, conn, params=params if params else None)
        conn.close()

        return {
            "source": "ONISR — scraping site officiel",
            "annee_filtre": annee,
            "nb_mois": len(df),
            "total_tues": int(df["tues_metropole"].sum()) if df["tues_metropole"].notna().any() else None,
            "barometre": df.to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")

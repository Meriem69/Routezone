"""
RouteZone -- Routes donnees BAAC (/accidents, /meteo, /onisr)
Competence C5 : API REST securisee
"""

from fastapi import APIRouter, Query, HTTPException, Depends
import math
import pandas as pd
from typing import Optional
from sqlalchemy import text

from db import engine
from security import verifier_api_key

router = APIRouter(tags=["Donnees BAAC"])


def nettoyer_df(df: pd.DataFrame) -> list:
    """DataFrame -> list[dict], NaN/Inf -> None pour serialisation JSON.

    df.where(notna, None) ne suffit pas : sur colonnes float, pandas
    coerce None en NaN. On nettoie cellule par cellule au niveau dict.
    """
    def _safe(v):
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v
    return [
        {k: _safe(v) for k, v in r.items()}
        for r in df.to_dict(orient="records")
    ]


# ── Accidents ────────────────────────────────────────────────────
@router.get("/accidents")
def liste_accidents(
    departement: Optional[str] = Query(None, description="Numero de departement (ex: 69)"),
    annee: Optional[int] = Query(None, description="Annee (2022, 2023 ou 2024)"),
    gravite: Optional[int] = Query(None, description="Gravite : 1=Indemne, 2=Tue, 3=Hospitalise, 4=Blesse leger"),
    limite: int = Query(100, description="Nombre max de resultats (max 1000)"),
    _: str = Depends(verifier_api_key),
):
    """Liste des accidents avec filtres optionnels."""
    if limite > 1000:
        limite = 1000

    params = {}
    if gravite:
        query = "SELECT DISTINCT a.* FROM accidents a JOIN usagers u ON a.num_acc = u.num_acc WHERE u.grav = :gravite"
        params["gravite"] = gravite
        if departement:
            query += " AND a.dep = :dep"; params["dep"] = departement
        if annee:
            query += " AND a.an = :annee"; params["annee"] = annee
    else:
        query = "SELECT * FROM accidents WHERE 1=1"
        if departement:
            query += " AND dep = :dep"; params["dep"] = departement
        if annee:
            query += " AND an = :annee"; params["annee"] = annee

    query += " LIMIT :limite"; params["limite"] = limite

    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params=params)
        return {"total": len(df), "filtres": {"departement": departement, "annee": annee, "gravite": gravite}, "accidents": nettoyer_df(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


@router.get("/accidents/stats")
def statistiques_globales(_: str = Depends(verifier_api_key)):
    """Statistiques globales : total, par annee, par gravite, top departements."""
    try:
        with engine.connect() as conn:
            total = pd.read_sql_query(text("SELECT COUNT(*) as total FROM accidents"), conn)
            par_annee = pd.read_sql_query(text("SELECT an, COUNT(*) as nb_accidents FROM accidents GROUP BY an ORDER BY an"), conn)
            par_gravite = pd.read_sql_query(text("""
                SELECT grav, COUNT(*) as nb_usagers,
                    CASE grav WHEN 1 THEN 'Indemne' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Hospitalise' WHEN 4 THEN 'Blesse leger' ELSE 'Inconnu' END as libelle
                FROM usagers GROUP BY grav ORDER BY grav"""), conn)
            top_dep = pd.read_sql_query(text("SELECT dep, COUNT(*) as nb_accidents FROM accidents GROUP BY dep ORDER BY nb_accidents DESC LIMIT 10"), conn)
        return {"total_accidents": int(total["total"].iloc[0]), "par_annee": nettoyer_df(par_annee), "par_gravite": nettoyer_df(par_gravite), "top_10_departements": nettoyer_df(top_dep)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


@router.get("/accidents/departement/{dep}")
def accidents_par_departement(dep: str, annee: Optional[int] = Query(None), _: str = Depends(verifier_api_key)):
    """Statistiques d'accidents pour un departement."""
    query = """
        SELECT a.an, a.mois, COUNT(DISTINCT a.num_acc) as nb_accidents,
            SUM(CASE WHEN u.grav = 2 THEN 1 ELSE 0 END) as nb_tues,
            SUM(CASE WHEN u.grav = 3 THEN 1 ELSE 0 END) as nb_hospitalises,
            SUM(CASE WHEN u.grav = 4 THEN 1 ELSE 0 END) as nb_blesses_legers
        FROM accidents a LEFT JOIN usagers u ON a.num_acc = u.num_acc WHERE a.dep = :dep
    """
    params = {"dep": dep}
    if annee:
        query += " AND a.an = :annee"; params["annee"] = annee
    query += " GROUP BY a.an, a.mois ORDER BY a.an, a.mois"

    try:
        with engine.connect() as conn:
            check = pd.read_sql_query(text("SELECT COUNT(*) as nb FROM accidents WHERE dep = :dep"), conn, params={"dep": dep})
            if check["nb"].iloc[0] == 0:
                raise HTTPException(status_code=404, detail=f"Departement {dep} non trouve")
            df = pd.read_sql_query(text(query), conn, params=params)
        return {"departement": dep, "annee_filtre": annee, "total_accidents": int(df["nb_accidents"].sum()), "total_tues": int(df["nb_tues"].sum()), "stats_par_mois": nettoyer_df(df)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


@router.get("/accidents/gravite")
def repartition_gravite(annee: Optional[int] = Query(None), departement: Optional[str] = Query(None), _: str = Depends(verifier_api_key)):
    """Repartition par niveau de gravite."""
    query = """
        SELECT u.grav, CASE u.grav WHEN 1 THEN 'Indemne' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Hospitalise' WHEN 4 THEN 'Blesse leger' END as libelle,
            COUNT(*) as nb_usagers
        FROM usagers u JOIN accidents a ON u.num_acc = a.num_acc WHERE u.grav IS NOT NULL
    """
    params = {}
    if annee:
        query += " AND a.an = :annee"; params["annee"] = annee
    if departement:
        query += " AND a.dep = :dep"; params["dep"] = departement
    query += " GROUP BY u.grav ORDER BY u.grav"

    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params=params)
        total = df["nb_usagers"].sum()
        df["pourcentage"] = (df["nb_usagers"] / total * 100).round(1)
        return {"filtres": {"annee": annee, "departement": departement}, "total_usagers": int(total), "repartition": nettoyer_df(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── Meteo ────────────────────────────────────────────────────────
@router.get("/meteo/stats")
def stats_meteo(_: str = Depends(verifier_api_key)):
    """Statistiques meteo (API Open-Meteo)."""
    try:
        with engine.connect() as conn:
            check = pd.read_sql_query(text("SELECT COUNT(*) as nb FROM meteo"), conn)
            if check["nb"].iloc[0] == 0:
                return {"message": "Table meteo vide"}
            stats = pd.read_sql_query(text("""
                SELECT COUNT(*) as nb_accidents_enrichis,
                    ROUND(AVG(temperature)::numeric, 1) as temp_moyenne, ROUND(MIN(temperature)::numeric, 1) as temp_min, ROUND(MAX(temperature)::numeric, 1) as temp_max,
                    ROUND(AVG(precipitation)::numeric, 2) as pluie_moyenne, ROUND(AVG(windspeed)::numeric, 1) as vent_moyen
                FROM meteo"""), conn)
        return {"source": "API Open-Meteo", "stats": nettoyer_df(stats)[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")


# ── ONISR ────────────────────────────────────────────────────────
@router.get("/onisr/barometre")
def barometre_onisr(annee: Optional[int] = Query(None), _: str = Depends(verifier_api_key)):
    """Barometre mensuel ONISR."""
    try:
        with engine.connect() as conn:
            check = pd.read_sql_query(text("SELECT COUNT(*) as nb FROM barometre_onisr"), conn)
            if check["nb"].iloc[0] == 0:
                return {"message": "Table barometre_onisr vide"}
            query = "SELECT titre, annee, mois, tues_metropole, date_publication FROM barometre_onisr"
            params = {}
            if annee:
                query += " WHERE annee = :annee"; params["annee"] = annee
            query += " ORDER BY annee, mois"
            df = pd.read_sql_query(text(query), conn, params=params if params else None)
        return {"source": "ONISR", "annee_filtre": annee, "nb_mois": len(df),
                "total_tues": int(df["tues_metropole"].sum()) if df["tues_metropole"].notna().any() else None,
                "barometre": nettoyer_df(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur BDD : {str(e)}")

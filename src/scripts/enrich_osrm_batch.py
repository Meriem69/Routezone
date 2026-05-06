"""
Enrichit le dataset BAAC avec les vrais temps OSRM (pompiers + SAU)
en orchestrant Docker region par region pour tenir dans 16 Go de RAM.

Pipeline par region :
  1. Telecharger le PBF Geofabrik
  2. osrm-extract / partition / customize
  3. Demarrer osrm-routed
  4. Pour chaque accident de la region :
       - top-K candidats Haversine pompiers + top-K candidats Haversine SAU
       - 1 appel /table OSRM (1 source, 2K destinations)
       - garder min(pompiers) et min(SAU)
  5. Sauvegarder data/processed/temps_intervention_osrm_<region>.csv
  6. Stopper le container
A la fin : concatenation des CSV regionaux + jointure avec Haversine V1.

Usage :
    python src/scripts/enrich_osrm_batch.py --regions ile-de-france
    python src/scripts/enrich_osrm_batch.py --regions ile-de-france,rhone-alpes
    python src/scripts/enrich_osrm_batch.py --regions all
    python src/scripts/enrich_osrm_batch.py --regions all --top-k 10 --keep-pbf
"""
import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "processed"
OUT_DIR = DATA_DIR / "osrm_regional"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OSRM_IMAGE = "ghcr.io/project-osrm/osrm-backend"
VOLUME_NAME = "routezone_osrm_batch"
CONTAINER = "routezone_osrm_batch_routed"
OSRM_PORT = 5001  # ne pas entrer en conflit avec prod 5000

GEOFABRIK_BASE = "https://download.geofabrik.de/europe/france"

# Mapping departement (code BAAC) -> region Geofabrik
# BAAC code dep en float (1.0..95.0), Corse = 201 (2A) / 202 (2B) / 20
DEPT_TO_REGION = {
    # Alsace
    67: "alsace", 68: "alsace",
    # Aquitaine
    24: "aquitaine", 33: "aquitaine", 40: "aquitaine", 47: "aquitaine", 64: "aquitaine",
    # Auvergne
    3: "auvergne", 15: "auvergne", 43: "auvergne", 63: "auvergne",
    # Basse-Normandie
    14: "basse-normandie", 50: "basse-normandie", 61: "basse-normandie",
    # Bourgogne
    21: "bourgogne", 58: "bourgogne", 71: "bourgogne", 89: "bourgogne",
    # Bretagne
    22: "bretagne", 29: "bretagne", 35: "bretagne", 56: "bretagne",
    # Centre
    18: "centre", 28: "centre", 36: "centre", 37: "centre", 41: "centre", 45: "centre",
    # Champagne-Ardenne
    8: "champagne-ardenne", 10: "champagne-ardenne", 51: "champagne-ardenne", 52: "champagne-ardenne",
    # Corse
    20: "corse", 201: "corse", 202: "corse",
    # Franche-Comte
    25: "franche-comte", 39: "franche-comte", 70: "franche-comte", 90: "franche-comte",
    # Haute-Normandie
    27: "haute-normandie", 76: "haute-normandie",
    # Ile-de-France
    75: "ile-de-france", 77: "ile-de-france", 78: "ile-de-france",
    91: "ile-de-france", 92: "ile-de-france", 93: "ile-de-france",
    94: "ile-de-france", 95: "ile-de-france",
    # Languedoc-Roussillon
    11: "languedoc-roussillon", 30: "languedoc-roussillon", 34: "languedoc-roussillon",
    48: "languedoc-roussillon", 66: "languedoc-roussillon",
    # Limousin
    19: "limousin", 23: "limousin", 87: "limousin",
    # Lorraine
    54: "lorraine", 55: "lorraine", 57: "lorraine", 88: "lorraine",
    # Midi-Pyrenees
    9: "midi-pyrenees", 12: "midi-pyrenees", 31: "midi-pyrenees", 32: "midi-pyrenees",
    46: "midi-pyrenees", 65: "midi-pyrenees", 81: "midi-pyrenees", 82: "midi-pyrenees",
    # Nord-Pas-de-Calais
    59: "nord-pas-de-calais", 62: "nord-pas-de-calais",
    # Pays-de-la-Loire
    44: "pays-de-la-loire", 49: "pays-de-la-loire", 53: "pays-de-la-loire",
    72: "pays-de-la-loire", 85: "pays-de-la-loire",
    # Picardie
    2: "picardie", 60: "picardie", 80: "picardie",
    # Poitou-Charentes
    16: "poitou-charentes", 17: "poitou-charentes", 79: "poitou-charentes", 86: "poitou-charentes",
    # Provence-Alpes-Cote-d-Azur
    4: "provence-alpes-cote-d-azur", 5: "provence-alpes-cote-d-azur",
    6: "provence-alpes-cote-d-azur", 13: "provence-alpes-cote-d-azur",
    83: "provence-alpes-cote-d-azur", 84: "provence-alpes-cote-d-azur",
    # Rhone-Alpes
    1: "rhone-alpes", 7: "rhone-alpes", 26: "rhone-alpes", 38: "rhone-alpes",
    42: "rhone-alpes", 69: "rhone-alpes", 73: "rhone-alpes", 74: "rhone-alpes",
}

ALL_REGIONS = sorted(set(DEPT_TO_REGION.values()))

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def haversine_vec(lat1, lon1, lats2, lons2):
    R = 6371
    la1, lo1 = np.radians(lat1), np.radians(lon1)
    la2, lo2 = np.radians(lats2), np.radians(lons2)
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def normalize_dep(d):
    """BAAC dep est en float64 ; on retourne un int avec gestion Corse."""
    if pd.isna(d):
        return None
    try:
        return int(float(d))
    except (TypeError, ValueError):
        s = str(d).strip().upper()
        if s == "2A":
            return 201
        if s == "2B":
            return 202
        return None


def docker(args, *, capture=True, check=True):
    return subprocess.run(["docker", *args], capture_output=capture, text=True, check=check)


def docker_quiet(args):
    """Exec docker en silence (errors ignored)."""
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def volume_init():
    docker_quiet(["volume", "create", VOLUME_NAME])


def file_in_volume(path):
    """Verifie si /data/<path> existe dans le volume."""
    r = docker_quiet(["run", "--rm", "-v", f"{VOLUME_NAME}:/data", "alpine",
                      "test", "-f", f"/data/{path}"])
    return r.returncode == 0


def file_size_volume(path):
    r = docker_quiet(["run", "--rm", "-v", f"{VOLUME_NAME}:/data", "alpine",
                      "stat", "-c", "%s", f"/data/{path}"])
    if r.returncode == 0:
        return int(r.stdout.strip())
    return 0


def download_pbf(region):
    """Telecharge le PBF de la region dans le volume si absent."""
    pbf = f"{region}-latest.osm.pbf"
    if file_in_volume(pbf):
        size_mb = file_size_volume(pbf) / 1024 / 1024
        print(f"  PBF deja present ({size_mb:.0f} MB).")
        return
    url = f"{GEOFABRIK_BASE}/{region}-latest.osm.pbf"
    print(f"  Telechargement PBF {region}...")
    r = docker(["run", "--rm", "-v", f"{VOLUME_NAME}:/data",
                "alpine", "sh", "-c",
                f"apk add --no-cache wget >/dev/null 2>&1 && wget -O /data/{pbf} {url}"],
               capture=False, check=True)


def osrm_prepare(region):
    """osrm-extract + partition + customize si .osrm pas encore prepare."""
    osrm = f"{region}-latest.osrm"
    pbf = f"{region}-latest.osm.pbf"
    # .osrm.mldgr est le dernier fichier produit par osrm-customize
    if file_in_volume(f"{osrm}.mldgr"):
        print(f"  OSRM deja prepare.")
        return
    print(f"  osrm-extract...")
    docker(["run", "--rm", "-v", f"{VOLUME_NAME}:/data", OSRM_IMAGE,
            "osrm-extract", "-p", "/opt/car.lua", f"/data/{pbf}"],
           capture=False, check=True)
    print(f"  osrm-partition...")
    docker(["run", "--rm", "-v", f"{VOLUME_NAME}:/data", OSRM_IMAGE,
            "osrm-partition", f"/data/{osrm}"], capture=False, check=True)
    print(f"  osrm-customize...")
    docker(["run", "--rm", "-v", f"{VOLUME_NAME}:/data", OSRM_IMAGE,
            "osrm-customize", f"/data/{osrm}"], capture=False, check=True)


def stop_container():
    docker_quiet(["rm", "-f", CONTAINER])


def start_osrm(region, sample_lat, sample_lon):
    """Demarre osrm-routed en daemon, attend qu'il reponde."""
    stop_container()
    osrm = f"/data/{region}-latest.osrm"
    docker(["run", "-d", "--name", CONTAINER,
            "-v", f"{VOLUME_NAME}:/data",
            "-p", f"{OSRM_PORT}:5000",
            OSRM_IMAGE, "osrm-routed", "--algorithm", "mld", osrm],
           check=True)
    print(f"  Attente osrm-routed sur port {OSRM_PORT}...")
    url_test = (f"http://localhost:{OSRM_PORT}/route/v1/driving/"
                f"{sample_lon},{sample_lat};{sample_lon + 0.01},{sample_lat + 0.01}")
    for i in range(120):
        try:
            r = requests.get(url_test, timeout=2)
            if r.status_code == 200 and r.json().get("code") in ("Ok", "NoRoute", "NoSegment"):
                print(f"  OSRM pret apres {i + 1}s.")
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f"  ERREUR : OSRM n'a pas repondu en 120s.")
    return False


def osrm_table(lat, lon, dest_coords):
    """1 source -> N destinations, retourne la liste de durees en secondes (None si unreachable)."""
    coords = f"{lon},{lat};" + ";".join(f"{ln},{lt}" for lt, ln in dest_coords)
    dests = ";".join(str(i + 1) for i in range(len(dest_coords)))
    url = (f"http://localhost:{OSRM_PORT}/table/v1/driving/{coords}"
           f"?sources=0&destinations={dests}&annotations=duration")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("code") != "Ok":
            return None
        return data["durations"][0]
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Process une region
# ----------------------------------------------------------------------------
def process_region(region, accidents, centres_pomp, centres_sau, top_k):
    """Retourne DataFrame [Num_Acc, nearest_pompiers_min_osrm, nearest_sau_min_osrm]."""
    pomp = centres_pomp[["lat", "lon"]].values
    sau = centres_sau[["lat", "lon"]].values
    n_pomp_k = min(top_k, len(pomp))
    n_sau_k = min(top_k, len(sau))

    rows = []
    n_unreachable = 0
    for _, acc in tqdm(accidents.iterrows(), total=len(accidents), desc=f"  {region}"):
        lat, lon = acc["lat"], acc["long"]
        d_p = haversine_vec(lat, lon, pomp[:, 0], pomp[:, 1])
        d_s = haversine_vec(lat, lon, sau[:, 0], sau[:, 1])
        idx_p = np.argpartition(d_p, n_pomp_k - 1)[:n_pomp_k]
        idx_s = np.argpartition(d_s, n_sau_k - 1)[:n_sau_k]

        dest_p = [(pomp[i, 0], pomp[i, 1]) for i in idx_p]
        dest_s = [(sau[i, 0], sau[i, 1]) for i in idx_s]
        durations = osrm_table(lat, lon, dest_p + dest_s)

        if durations is None:
            n_unreachable += 1
            rows.append({"Num_Acc": acc["Num_Acc"],
                         "nearest_pompiers_min_osrm": np.nan,
                         "nearest_sau_min_osrm": np.nan})
            continue

        durs = np.array([d if d is not None else np.nan for d in durations], dtype=float)
        d_p_osrm = durs[:n_pomp_k]
        d_s_osrm = durs[n_pomp_k:]
        v_p = d_p_osrm[~np.isnan(d_p_osrm)]
        v_s = d_s_osrm[~np.isnan(d_s_osrm)]
        rows.append({
            "Num_Acc": acc["Num_Acc"],
            "nearest_pompiers_min_osrm": round(v_p.min() / 60, 2) if len(v_p) else np.nan,
            "nearest_sau_min_osrm": round(v_s.min() / 60, 2) if len(v_s) else np.nan,
        })

    if n_unreachable:
        print(f"  {n_unreachable} accidents sans reponse OSRM (NaN)")
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Concat final
# ----------------------------------------------------------------------------
def concat_results():
    """Concatene tous les CSV regionaux + merge avec Haversine pour comparaison."""
    parts = sorted(OUT_DIR.glob("temps_intervention_osrm_*.csv"))
    if not parts:
        print("Aucun CSV regional trouve.")
        return
    df_osrm = pd.concat([pd.read_csv(p) for p in parts], ignore_index=True)
    df_osrm = df_osrm.drop_duplicates(subset=["Num_Acc"], keep="first")
    df_osrm["temps_total_osrm"] = df_osrm["nearest_pompiers_min_osrm"] + df_osrm["nearest_sau_min_osrm"]

    hav_path = DATA_DIR / "temps_intervention.csv"
    if hav_path.exists():
        df_hav = pd.read_csv(hav_path)
        # Renommer Haversine pour clarifier
        rename = {}
        if "nearest_pompiers_min" in df_hav.columns:
            rename["nearest_pompiers_min"] = "nearest_pompiers_min_hav"
        if "nearest_sau_min" in df_hav.columns:
            rename["nearest_sau_min"] = "nearest_sau_min_hav"
        if "temps_total_prise_en_charge" in df_hav.columns:
            rename["temps_total_prise_en_charge"] = "temps_total_hav"
        df_hav = df_hav.rename(columns=rename)
        keep = ["Num_Acc"] + [v for v in rename.values()]
        keep = [c for c in keep if c in df_hav.columns]
        df_hav = df_hav[keep].drop_duplicates(subset=["Num_Acc"], keep="first")
        df_full = df_osrm.merge(df_hav, on="Num_Acc", how="left")
    else:
        df_full = df_osrm

    # Deltas (OSRM - Haversine) si dispo
    if "temps_total_hav" in df_full.columns:
        df_full["delta_total"] = df_full["temps_total_osrm"] - df_full["temps_total_hav"]

    out = DATA_DIR / "temps_intervention_osrm.csv"
    df_full.to_csv(out, index=False)
    print(f"\n=> {out}  ({len(df_full):,} accidents)")
    print(df_full.describe(include="all").T[["mean", "50%", "min", "max"]].round(1))


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", default="ile-de-france",
                    help="liste virgule-separee, ou 'all'")
    ap.add_argument("--top-k", type=int, default=10,
                    help="nb candidats Haversine par categorie")
    ap.add_argument("--keep-pbf", action="store_true",
                    help="ne pas supprimer le PBF apres traitement")
    ap.add_argument("--concat-only", action="store_true",
                    help="seulement concatener les CSV regionaux deja produits")
    args = ap.parse_args()

    if args.concat_only:
        concat_results()
        return

    if args.regions == "all":
        regions = ALL_REGIONS
    else:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]
        unknown = [r for r in regions if r not in ALL_REGIONS]
        if unknown:
            print(f"Regions inconnues : {unknown}")
            print(f"Disponibles : {ALL_REGIONS}")
            sys.exit(1)

    print(f"Regions a traiter : {regions}")
    print(f"Top-K Haversine   : {args.top_k}")

    # Cleanup container si Ctrl+C
    def _sigint(*_):
        print("\n[interruption] arret du container OSRM...")
        stop_container()
        sys.exit(130)
    signal.signal(signal.SIGINT, _sigint)

    # Init volume Docker
    volume_init()

    # Data
    print("Chargement dataset_clean.csv...")
    df = pd.read_csv(DATA_DIR / "dataset_clean.csv",
                     usecols=["Num_Acc", "lat", "long", "dep"], low_memory=False)
    df = df.dropna(subset=["lat", "long", "dep"])
    # 1 ligne par accident (le dataset a 1 ligne par usager)
    df = df.drop_duplicates(subset=["Num_Acc"], keep="first")
    df["dep_int"] = df["dep"].apply(normalize_dep)
    df["region"] = df["dep_int"].map(DEPT_TO_REGION)
    print(f"  {len(df):,} accidents avec GPS+dep, "
          f"{df['region'].notna().sum():,} avec region connue")

    # Sources : casernes_france.csv pour pompiers (5906), centres_urgences.csv pour SAU (638)
    # On utilise les memes sources que la V1 Haversine pour une comparaison apples-to-apples
    casernes = pd.read_csv(ROOT / "data" / "raw" / "casernes_france.csv", low_memory=False)
    centres_pomp = casernes[["lat", "lon"]].dropna()
    centres = pd.read_csv(DATA_DIR / "centres_urgences.csv")
    centres_sau = centres[centres["type"] == "urgences_sau"][["lat", "lon"]].dropna()
    print(f"  Pompiers : {len(centres_pomp):,}  |  SAU : {len(centres_sau):,}")

    for region in regions:
        out_csv = OUT_DIR / f"temps_intervention_osrm_{region}.csv"
        print(f"\n=== {region} ===")
        if out_csv.exists():
            print(f"  CSV deja present, skip ({out_csv}).")
            continue

        accidents = df[df["region"] == region].copy()
        print(f"  {len(accidents):,} accidents dans cette region")
        if len(accidents) == 0:
            print(f"  Aucun accident, skip.")
            continue

        try:
            osrm_ready = file_in_volume(f"{region}-latest.osrm.mldgr")
            if not osrm_ready:
                download_pbf(region)
                osrm_prepare(region)
            else:
                print(f"  OSRM deja prepare (skip download+extract).")
            sample_lat, sample_lon = accidents.iloc[0][["lat", "long"]]
            if not start_osrm(region, sample_lat, sample_lon):
                print(f"  [skip] OSRM ne demarre pas pour {region}")
                continue
            df_out = process_region(region, accidents, centres_pomp, centres_sau, args.top_k)
            df_out.to_csv(out_csv, index=False)
            print(f"  -> {out_csv}  ({len(df_out):,} lignes)")
        finally:
            stop_container()

        if not args.keep_pbf:
            # Supprimer le PBF (libere disque, le .osrm reste pour reproductibilite)
            docker_quiet(["run", "--rm", "-v", f"{VOLUME_NAME}:/data", "alpine",
                          "rm", "-f", f"/data/{region}-latest.osm.pbf"])

    concat_results()


if __name__ == "__main__":
    main()

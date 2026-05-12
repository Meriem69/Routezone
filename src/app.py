import streamlit as st
import requests
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, AntPath, MarkerCluster
from streamlit_folium import st_folium
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
import base64
import datetime as dt
import json
import os

st.set_page_config(
    page_title="RouteZone",
    page_icon="🚦",
    layout="wide"
)

# ── Configuration API ────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://127.0.0.1:8001")
API_KEY = os.getenv("API_KEY", "routezone-secret-2024")

# ── Session state (auth) ────────────────────────────────────────────────────
if "jwt_token" not in st.session_state:
    st.session_state.jwt_token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "page" not in st.session_state:
    st.session_state.page = "prediction"
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_routes" not in st.session_state:
    st.session_state.last_routes = None
if "last_best" not in st.session_state:
    st.session_state.last_best = None
if "last_coords" not in st.session_state:
    st.session_state.last_coords = None
if "geo_lat" not in st.session_state:
    st.session_state.geo_lat = 48.8566
if "geo_lon" not in st.session_state:
    st.session_state.geo_lon = 2.3522
if "geo_label" not in st.session_state:
    st.session_state.geo_label = ""
if "agg_inferred" not in st.session_state:
    st.session_state.agg_inferred = None  # 1 = hors, 2 = en agglo, None = pas detecte
if "vma_inferred" not in st.session_state:
    st.session_state.vma_inferred = None


# OSRM : Docker local si dispo, sinon API publique
OSRM_LOCAL = "http://localhost:5000"
OSRM_PUBLIC = "https://router.project-osrm.org"

def get_osrm_url():
    """Teste le Docker local, sinon fallback API publique."""
    try:
        r = requests.get(f"{OSRM_LOCAL}/route/v1/driving/2.35,48.85;2.29,48.86", timeout=2)
        if r.status_code == 200:
            return OSRM_LOCAL
    except Exception:
        pass
    return OSRM_PUBLIC

OSRM_URL = os.getenv("OSRM_URL", get_osrm_url())

def api_headers():
    """Retourne les headers avec API key + JWT si connecte."""
    h = {"X-API-Key": API_KEY}
    if st.session_state.jwt_token:
        h["Authorization"] = f"Bearer {st.session_state.jwt_token}"
    return h

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


@st.cache_data(ttl=3600, show_spinner=False)
def geocode_ban(address: str):
    """Geocode adresse via API BAN. Retourne dict {lat, lon, label, type, city, citycode}."""
    if not address or not address.strip():
        return None
    try:
        r = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": address.strip(), "limit": 1},
            timeout=5,
        )
        if r.ok:
            features = r.json().get("features", [])
            if features:
                f = features[0]
                lon, lat = f["geometry"]["coordinates"]
                p = f["properties"]
                return {
                    "lat": float(lat),
                    "lon": float(lon),
                    "label": p.get("label", address),
                    "type": p.get("type", ""),         # housenumber / street / locality / municipality
                    "city": p.get("city", ""),
                    "citycode": p.get("citycode", ""), # code INSEE commune (5 chiffres)
                }
    except Exception:
        pass
    return None


def _infer_agg(geo: dict) -> int:
    """Devine si l'adresse est EN agglomeration (2) ou HORS agglo (1).
    Heuristique :
    - type 'housenumber' (numero de rue) -> dans une rue urbaine -> agg=2
    - type 'street'                       -> rue identifiee -> agg=2
    - type 'municipality' (centre commune)-> centre-ville -> agg=2
    - type 'locality' (lieu-dit)          -> hameau rural -> agg=1
    Source : doc API BAN data.gouv.fr.
    """
    t = (geo or {}).get("type", "")
    if t in ("housenumber", "street", "municipality"):
        return 2
    if t == "locality":
        return 1
    return 2  # defaut prudent : la majorite des adresses BAN sont urbaines


def _infer_vma(agg: int, catr: int) -> int:
    """Devine la VMA selon agglo + categorie de route. Defaut 50 si en doute."""
    if catr == 1:           # autoroute
        return 130
    if catr == 2:           # nationale
        return 110 if agg == 1 else 50
    if catr == 3:           # departementale
        return 80 if agg == 1 else 50
    if agg == 2:            # quasi tout le reste en ville
        return 50
    return 80               # rural par defaut


@st.cache_data(ttl=3600, show_spinner=False)
def get_weather_from_openmeteo(lat, lon, jour: int, mois: int, annee: int):
    """Recupere temperature / precipitations / vent via Open-Meteo.

    - Si lat/lon manquants ou API en erreur -> fallback (15.0, 0.0, 10.0).
    - Date >7 jours dans le passe -> endpoint archive ; sinon forecast.
    - Renvoie (temperature [°C], precipitation [mm], windspeed [km/h]).

    Note sur l'annee : l'utilisateur la saisit dans le formulaire
    (champ "Annee" dans la section "Donnees temporelles"). La meteo
    est donc recuperee a la date exacte jour/mois/annee fournie.
    Si l'annee est dans le passe (>7j) on utilise l'API archive ;
    sinon l'API forecast (qui couvre aussi les jours recents).
    """
    fallback = (15.0, 0.0, 10.0)
    if lat is None or lon is None:
        return fallback
    try:
        year = int(annee)
        try:
            target = dt.date(year, int(mois), int(jour))
        except (ValueError, TypeError):
            target = dt.date(year, int(mois) if 1 <= int(mois) <= 12 else 6, 15)
        today = dt.date.today()
        if target < today - dt.timedelta(days=7):
            url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": float(lat),
            "longitude": float(lon),
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "daily": "temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
            "timezone": "Europe/Paris",
        }
        r = requests.get(url, params=params, timeout=5)
        if r.status_code != 200:
            return fallback
        daily = r.json().get("daily", {})
        temp = daily.get("temperature_2m_mean", [None])[0]
        prec = daily.get("precipitation_sum", [None])[0]
        wind = daily.get("wind_speed_10m_max", [None])[0]
        return (
            float(temp) if temp is not None else fallback[0],
            float(prec) if prec is not None else fallback[1],
            float(wind) if wind is not None else fallback[2],
        )
    except Exception:
        return fallback


@st.cache_data(show_spinner=False)
def load_zones_blanches():
    """Charge les zones blanches OSRM precalculees (>30 min temps total)."""
    p = Path(__file__).parent.parent / "data" / "processed" / "zones_blanches_osrm.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df[["lat", "long", "temps_total_osrm"]].dropna()


@st.cache_data(show_spinner=False)
def load_all_casernes():
    """Charge les 5906 casernes pompiers (CIS) depuis casernes_france.csv."""
    p = Path(__file__).parent.parent / "data" / "raw" / "casernes_france.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    keep = [c for c in ["nom", "ville", "departement", "lat", "lon"] if c in df.columns]
    return df[keep].dropna(subset=["lat", "lon"])


@st.cache_data(show_spinner=False)
def load_all_sau():
    """Charge les SAU/CHU depuis centres_urgences.csv (filtre type=urgences_sau)."""
    p = Path(__file__).parent.parent / "data" / "processed" / "centres_urgences.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df = df[df["type"] == "urgences_sau"]
    return df[["nom", "lat", "lon"]].dropna(subset=["lat", "lon"])

def compute_nearest_centres(lat, lon, n_per_type=2):
    """Trouve les n_per_type pompiers + n_per_type SAU les plus proches.

    Sources distinctes :
    - Pompiers : data/raw/casernes_france.csv (5906 CIS, source Overpass/OSM)
    - SAU      : data/processed/centres_urgences.csv (638 CHU, source data.gouv.fr)

    Pour les pompiers : route OSRM DEPUIS la caserne VERS l'accident (direction reelle).
    Pour les SAU      : route OSRM DEPUIS l'accident VERS l'hopital (evacuation).
    Cela donne la chaine Golden Hour complete : pompier -> accident -> SAU.
    """
    base = Path(__file__).parent.parent / "data"
    pompiers_path = base / "raw" / "casernes_france.csv"
    sau_path = base / "processed" / "centres_urgences.csv"
    if not pompiers_path.exists() or not sau_path.exists():
        return None, None, None

    df_pomp = pd.read_csv(pompiers_path).dropna(subset=["lat", "lon"])
    df_pomp["type"] = "pompiers"
    df_sau_raw = pd.read_csv(sau_path)
    df_sau = df_sau_raw[df_sau_raw["type"] == "urgences_sau"].dropna(subset=["lat", "lon"]).copy()
    centres = pd.concat([df_pomp[["nom", "lat", "lon", "type"]],
                         df_sau[["nom", "lat", "lon", "type"]]],
                        ignore_index=True)

    routes = []
    top_centres = []

    for ctype in ("pompiers", "urgences_sau"):
        sub = centres[centres["type"] == ctype].copy()
        if sub.empty:
            continue
        sub["dist_hav"] = sub.apply(
            lambda r: _haversine(lat, lon, r["lat"], r["lon"]), axis=1
        )
        top = sub.nsmallest(n_per_type, "dist_hav").reset_index(drop=True)
        top_centres.append(top)

        for _, c in top.iterrows():
            # Direction reelle : pompiers viennent VERS la victime, SAU est destination
            if ctype == "pompiers":
                src_lat, src_lon = c["lat"], c["lon"]
                dst_lat, dst_lon = lat, lon
            else:
                src_lat, src_lon = lat, lon
                dst_lat, dst_lon = c["lat"], c["lon"]

            route_info = {
                "nom": c["nom"], "type": ctype,
                "lat": c["lat"], "lon": c["lon"],   # position du centre (pour le marqueur)
                "direction": "pompier_vers_accident" if ctype == "pompiers" else "accident_vers_sau",
            }
            try:
                r = requests.get(
                    f"{OSRM_URL}/route/v1/driving/{src_lon},{src_lat};{dst_lon},{dst_lat}",
                    params={"overview": "full", "geometries": "geojson"},
                    timeout=5,
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        route = data["routes"][0]
                        route_info["duration_min"] = round(route["duration"] / 60, 1)
                        route_info["distance_km"] = round(route["distance"] / 1000, 1)
                        # geometry = liste de [lon, lat] dans le sens src -> dst
                        route_info["geometry"] = route["geometry"]["coordinates"]
                        routes.append(route_info)
                        continue
            except Exception:
                pass
            # Fallback Haversine
            d = c["dist_hav"] * 1.3
            route_info["duration_min"] = round(d / 60 * 60, 1)
            route_info["distance_km"] = round(d, 1)
            route_info["geometry"] = None
            routes.append(route_info)

    # Best par type (le plus rapide de chaque categorie)
    pomp_routes = [r for r in routes if r["type"] == "pompiers"]
    sau_routes = [r for r in routes if r["type"] == "urgences_sau"]
    best_pomp = min(pomp_routes, key=lambda r: r["duration_min"]) if pomp_routes else None
    best_sau = min(sau_routes, key=lambda r: r["duration_min"]) if sau_routes else None
    # Backward compat : best = celui qui contribue le plus (le plus lent des deux limites le total)
    if best_pomp and best_sau:
        best = best_pomp if best_pomp["duration_min"] >= best_sau["duration_min"] else best_sau
    else:
        best = best_pomp or best_sau

    top_concat = pd.concat(top_centres, ignore_index=True) if top_centres else None
    return routes, best, top_concat

# ── Image hero ────────────────────────────────────────────────────────────────
HERO_IMAGE = Path(__file__).parent / "anthony-maw-XcjVef6uvYA-unsplash.jpg"

@st.cache_data
def load_hero_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

if HERO_IMAGE.exists():
    img_b64 = load_hero_image(str(HERO_IMAGE))
    hero_css = f"background-image: linear-gradient(to bottom, rgba(10,14,26,0.45) 0%, rgba(10,14,26,0.82) 65%, #0a0e1a 100%), url('data:image/jpeg;base64,{img_b64}');"
else:
    hero_css = "background: linear-gradient(135deg, #1a0808 0%, #0a0e1a 100%);"

# ── SVG icons ─────────────────────────────────────────────────────────────────
def svg(path_d, extra="", w=14, h=14, color="#94a3b8", viewBox="0 0 24 24"):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{viewBox}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{path_d}{extra}</svg>'

ICONS = {
    # sections
    "traffic":  '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><circle cx="12" cy="7" r="2" fill="#ef4444" stroke="none"/><circle cx="12" cy="12" r="2" fill="#f59e0b" stroke="none"/><circle cx="12" cy="17" r="2" fill="#22c55e" stroke="none"/></svg>',
    "warning":  svg('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>', color="#f97316", w=15, h=15),
    "person":   svg('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>', color="#f97316", w=15, h=15),
    "calendar": svg('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>', color="#f97316", w=15, h=15),
    # champs
    "sun":      svg('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'),
    "map-pin":  svg('<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>'),
    "cloud":    svg('<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>'),
    "zap":      svg('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'),
    "road":     svg('<line x1="12" y1="22" x2="12" y2="2"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'),
    "user":     svg('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
    "users":    svg('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "car":      svg('<rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4l3 5v3h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>'),
    "shield":   svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
    "compass":  svg('<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>'),
    "age":      svg('<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><line x1="12" y1="14" x2="12" y2="22"/>'),
    "clock":    svg('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'),
    "month":    svg('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="14" x2="8" y2="14"/><line x1="12" y1="14" x2="12" y2="14"/><line x1="16" y1="14" x2="16" y2="14"/>'),
    "gauge":    svg('<path d="M12 22a10 10 0 1 0-10-10"/><path d="M12 12l4-4"/>'),
}

def section_label(key, text):
    return f'<div class="section-label">{ICONS[key]}{text}</div>'

def field_label(key, text, required=False, optional=False):
    """Rend un label de champ. required=True ajoute un astérisque rouge accessible
    (aria-label), optional=True ajoute '(facultatif)' en gris italique."""
    suffix = ""
    if required:
        suffix = '<span class="required-asterisk" aria-label="champ obligatoire"> *</span>'
    elif optional:
        suffix = '<span class="optional-tag"> (facultatif)</span>'
    return f'<div class="field-label">{ICONS[key]}<span>{text}{suffix}</span></div>'

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&display=swap');

.stApp {{
    background: #0a0e1a;
    font-family: 'DM Sans', sans-serif;
}}
header[data-testid="stHeader"] {{ background: transparent !important; }}
.stDeployButton {{ display: none; }}
#MainMenu {{ visibility: hidden; }}

/* ── HERO ── */
.hero-banner {{
    width: 100vw;
    min-height: 270px;
    {hero_css}
    background-size: cover;
    background-position: center 40%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 2.5rem 3rem 2.2rem;
    margin: -4rem calc(-50vw + 50%) 2rem calc(-50vw + 50%);
    border-bottom: 2px solid #f97316;
    box-sizing: border-box;
}}
.hero-badge {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(249,115,22,0.18);
    border: 1px solid rgba(249,115,22,0.45);
    color: #f97316;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 12px;
    width: fit-content;
}}
.hero-title {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(2.4rem, 5.5vw, 4rem);
    letter-spacing: 5px;
    background: linear-gradient(90deg, #ffffff 0%, #fdba74 55%, #ef4444 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.05;
    margin: 0 0 10px 0;
}}
.hero-sub {{
    color: #94a3b8;
    font-size: 0.9rem;
    font-weight: 300;
    letter-spacing: 0.4px;
}}

/* ── SECTION LABELS ── */
.section-label {{
    color: #f97316;
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin: 1.4rem 0 0.4rem;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.section-label::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, #334155 0%, transparent 100%);
}}

/* ── FIELD LABELS custom ── */
.field-label {{
    display: flex;
    align-items: center;
    gap: 6px;
    color: #94a3b8;
    font-size: 0.74rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 4px;
    margin-top: 0.6rem;
}}
.field-label span {{ line-height: 1; }}

/* Masquer les vrais labels Streamlit quand on utilise field-label */
.hide-label label {{ display: none !important; }}

/* ── LABELS natifs (fallback) ── */
label, .stSelectbox label, .stNumberInput label {{
    color: #94a3b8 !important;
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
}}

/* ── SELECTBOX ── */
.stSelectbox > div > div {{
    background-color: #111827 !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    transition: border-color 0.2s, box-shadow 0.2s;
}}
.stSelectbox > div > div:hover {{ border-color: #f97316 !important; }}
.stSelectbox > div > div:focus-within {{
    border-color: #f97316 !important;
    box-shadow: 0 0 0 2px rgba(249,115,22,0.18) !important;
}}
.stSelectbox svg {{ fill: #f97316 !important; }}
div[data-baseweb="popover"] {{
    background: #111827 !important;
    border: 1px solid #1e293b !important;
    border-radius: 10px !important;
}}
li[role="option"] {{
    color: #cbd5e1 !important;
    background: #111827 !important;
    font-size: 0.87rem !important;
}}
li[role="option"]:hover, li[aria-selected="true"] {{
    background: rgba(249,115,22,0.12) !important;
    color: #f97316 !important;
}}

/* ── NUMBER INPUT ── */
.stNumberInput > div > div > input {{
    background-color: #111827 !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px 0 0 8px !important;
    color: #e2e8f0 !important;
    text-align: center;
    font-size: 1.15rem !important;
    font-weight: 500 !important;
}}
.stNumberInput button {{
    background-color: #1e293b !important;
    border: 1px solid #1e293b !important;
    color: #f97316 !important;
    transition: all 0.15s;
}}
.stNumberInput button:hover {{
    background-color: #f97316 !important;
    color: #fff !important;
    border-color: #f97316 !important;
}}

/* ── DIVIDER ── */
hr {{
    border: none !important;
    border-top: 1px solid #1e293b !important;
    margin: 1.5rem 0 !important;
}}

/* ── BOUTON ── */
div[data-testid="stButton"] > button {{
    background: linear-gradient(135deg, #f97316 0%, #dc2626 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 1.15rem !important;
    letter-spacing: 2.5px !important;
    padding: 0.75rem 2rem !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 24px rgba(249,115,22,0.38) !important;
}}
div[data-testid="stButton"] > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 32px rgba(249,115,22,0.58) !important;
}}

/* ── ALERTES ── */
div[data-testid="stAlert"] {{
    border-radius: 12px !important;
    font-weight: 500 !important;
    font-size: 1rem !important;
    margin-top: 1rem !important;
}}

/* ── FOOTER ── */
.footer {{
    text-align: center;
    color: #e2e8f0;
    font-size: 0.75rem;
    letter-spacing: 1.5px;
    padding: 1rem 0 0.5rem;
    opacity: 0.7;
}}

/* ── SIDEBAR : aligner sur le dark theme du main ── */
section[data-testid="stSidebar"] {{
    background-color: #0a0e1a !important;
    border-right: 1px solid #1e293b !important;
}}
section[data-testid="stSidebar"] * {{
    color: #e2e8f0;
}}
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] [data-baseweb="input"] input {{
    background-color: #111827 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1e293b !important;
}}
section[data-testid="stSidebar"] label {{
    color: #cbd5e1 !important;
}}
section[data-testid="stSidebar"] .stRadio label {{
    color: #e2e8f0 !important;
}}

/* ── Sidebar : boutons accents orange au hover/focus ── */
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover,
section[data-testid="stSidebar"] .stButton > button:hover {{
    border-color: #f97316 !important;
    color: #f97316 !important;
}}
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:focus,
section[data-testid="stSidebar"] .stButton > button:focus {{
    outline: 2px solid #f97316 !important;
    outline-offset: 2px !important;
}}

/* ── Sidebar : carte "Connecté" avec accent orange ── */
.connected-card {{
    background: rgba(249,115,22,0.12);
    border: 1px solid #f97316;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0 1rem;
    color: #fff;
}}
.connected-card-label {{
    font-size: 0.7rem;
    color: #f97316;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 4px;
}}
.connected-card-email {{
    color: #fdba74;
    font-size: 0.85rem;
    word-break: break-all;
}}

/* ── Marqueurs obligatoire / facultatif ── */
.required-asterisk {{
    color: #dc2626;
    margin-left: 4px;
    font-weight: 700;
}}
.optional-tag {{
    color: #94a3b8;
    font-style: italic;
    margin-left: 6px;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
}}
.legende-required {{
    color: #94a3b8;
    font-size: 0.72rem;
    margin: -0.2rem 0 1rem;
    text-align: right;
    font-style: italic;
}}

/* ── Carte météo "auto" plus visible que st.caption ── */
.meteo-card {{
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(56,189,248,0.10);
    border: 1px solid rgba(56,189,248,0.40);
    border-radius: 8px;
    padding: 0.7rem 1rem;
    color: #e0f2fe;
    margin: 0.6rem 0 0.4rem;
    font-size: 0.95rem;
}}
.meteo-card strong {{ color: #f97316; font-weight: 700; }}

/* ── Mode localisation : style tab-like pour le radio Adresse/GPS ── */
div[data-testid="stRadio"][aria-label*="ode"] > div,
.mode-loc-radio div[role="radiogroup"] {{
    display: flex !important;
    gap: 6px !important;
}}
.mode-loc-radio label {{
    flex: 1;
    border: 2px solid #1e293b !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    background: #0f172a !important;
    cursor: pointer !important;
    transition: all 0.15s ease;
    text-align: center;
}}
.mode-loc-radio label:hover {{
    border-color: #fb923c !important;
}}
.mode-loc-radio label:has(input:checked) {{
    border-color: #f97316 !important;
    background: rgba(249,115,22,0.18) !important;
    color: #f97316 !important;
    font-weight: 700;
    box-shadow: 0 0 0 1px #f97316;
}}

/* ── Focus accessibilite (RGAA) : visible au clavier ── */
button:focus-visible,
input:focus-visible,
[role="option"]:focus-visible,
[data-baseweb="select"] > div:focus-visible {{
    outline: 2px solid #f97316 !important;
    outline-offset: 2px !important;
}}

/* ── Contraste WCAG : remonter le gris des field-label ── */
.field-label {{ color: #cbd5e1 !important; }}
</style>
""", unsafe_allow_html=True)

# ── HERO ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero-banner">
    <div class="hero-badge">
        {ICONS['traffic']}
        RouteZone &nbsp;·&nbsp; IA Simplon × Microsoft &nbsp;·&nbsp; RNCP37827
    </div>
    <div class="hero-title">Prédiction de gravité<br>des accidents</div>
    <div class="hero-sub">Renseignez les caractéristiques d'un accident pour prédire sa gravité &nbsp;·&nbsp; Données BAAC 2022–2024</div>
</div>
""", unsafe_allow_html=True)

# ── FORMULAIRE ────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="legende-required">'
    '<span class="required-asterisk">*</span> champs obligatoires'
    '</div>',
    unsafe_allow_html=True,
)
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(section_label("warning", "Contexte de l'accident"), unsafe_allow_html=True)

    st.markdown(field_label("sun", "Luminosité", required=True), unsafe_allow_html=True)
    lum = st.selectbox("Luminosité", options=[1,2,3,4,5], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Plein jour", 2:"Crépuscule / aube",
            3:"Nuit sans éclairage", 4:"Nuit — éclairage non allumé",
            5:"Nuit — éclairage allumé"}[x])

    st.markdown(field_label("map-pin", "Localisation", required=True), unsafe_allow_html=True)
    _agg_opts = [1, 2]
    _agg_default_idx = _agg_opts.index(st.session_state.agg_inferred) if st.session_state.agg_inferred in _agg_opts else 0
    agg = st.selectbox(
        "Localisation",
        options=_agg_opts,
        index=_agg_default_idx,
        label_visibility="collapsed",
        format_func=lambda x: {1: "Hors agglomération", 2: "En agglomération"}[x],
        help="Auto-détecté depuis l'adresse si vous utilisez le mode Adresse" if st.session_state.agg_inferred else None,
    )

    st.markdown(field_label("cloud", "Conditions météo", required=True), unsafe_allow_html=True)
    atm = st.selectbox("Conditions météo", options=[1,2,3,4,5,6,7,8], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Normale", 2:"Pluie légère", 3:"Pluie forte",
            4:"Neige / grêle", 5:"Brouillard", 6:"Vent fort",
            7:"Temps éblouissant", 8:"Temps couvert"}[x])

    st.markdown(field_label("zap", "Type de collision", required=True), unsafe_allow_html=True)
    col_acc = st.selectbox("Type de collision", options=[1,2,3,4,5,6,7], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Frontale (2 véh.)", 2:"Par l'arrière (2 véh.)",
            3:"Par le côté (2 véh.)", 4:"En chaîne (3 véh.)",
            5:"Multiples (3 véh.)", 6:"Autre", 7:"Sans collision"}[x])

    st.markdown(field_label("road", "Catégorie de route", required=True), unsafe_allow_html=True)
    catr = st.selectbox("Catégorie de route", options=[1,2,3,4,5,6,7], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Autoroute", 2:"Route nationale", 3:"Route départementale",
            4:"Voie communale", 5:"Hors réseau public",
            6:"Parc de stationnement", 7:"Route métropole urbaine"}[x])

    st.markdown(field_label("gauge", "Vitesse max autorisée", required=True), unsafe_allow_html=True)
    vma = st.selectbox(
        "VMA", options=[30, 50, 70, 80, 90, 110, 130], index=1,
        label_visibility="collapsed",
        format_func=lambda x: f"{x} km/h",
    )

    st.markdown(field_label("cloud", "État de la surface", required=True), unsafe_allow_html=True)
    surf = st.selectbox(
        "Surface", options=[1, 2, 3, 4, 5, 6, 7, 8, 9],
        label_visibility="collapsed",
        format_func=lambda x: {
            1: "Normale", 2: "Mouillée", 3: "Flaques",
            4: "Inondée", 5: "Enneigée", 6: "Boue",
            7: "Verglacée", 8: "Corps gras / huile", 9: "Autre",
        }[x],
    )

with col2:
    st.markdown(section_label("person", "Profil de l'usager"), unsafe_allow_html=True)

    st.markdown(field_label("user", "Catégorie d'usager", required=True), unsafe_allow_html=True)
    catu = st.selectbox("Catégorie d'usager", options=[1,2,3,4], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Conducteur", 2:"Passager",
            3:"Piéton", 4:"Piéton en roller / trottinette"}[x])

    st.markdown(field_label("users", "Sexe", required=True), unsafe_allow_html=True)
    sexe = st.selectbox("Sexe", options=[1,2], label_visibility="collapsed",
        format_func=lambda x: {1:"Masculin", 2:"Féminin"}[x])

    st.markdown(field_label("car", "Catégorie de véhicule", required=True), unsafe_allow_html=True)
    catv = st.selectbox("Catégorie de véhicule",
        options=[7, 10, 1, 2, 30, 31, 32, 50, 60, 33, 34, 35, 36, 13, 14, 3, 99],
        label_visibility="collapsed",
        format_func=lambda x: {
            7:  "Voiture",
            10: "Utilitaire / Camionnette",
            1:  "Vélo",
            2:  "Scooter / Cyclomoteur",
            30: "Scooter 50cc",
            31: "Moto",
            32: "Moto avec side-car",
            50: "Trottinette électrique",
            60: "Trottinette / Roller",
            33: "Quad",
            34: "Quad lourd",
            35: "Bus / Car",
            36: "Autocar",
            13: "Poids lourd / Camion",
            14: "Camion + remorque",
            3:  "Voiture légère (3 places)",
            99: "Autre"}[x])

    st.markdown(field_label("shield", "Équipement de sécurité", required=True), unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.72rem;color:#475569;margin-bottom:4px;">Sélectionnez tout ce qui s\'applique</div>', unsafe_allow_html=True)
    secu_choices = st.multiselect("Équipement de sécurité",
        options=[0,1,2,3,4,5,6,7,9],
        default=[0],
        label_visibility="collapsed",
        format_func=lambda x: {
            0:"Aucun", 1:"Ceinture", 2:"Casque",
            3:"Siège enfant", 4:"Gilet réfléchissant",
            5:"Airbag moto", 6:"Gants moto",
            7:"Gants + Airbag moto", 9:"Autre"}[x])
    # On garde le premier équipement coché pour le modèle (secu1)
    # Si "Aucun" est parmi les choix avec d'autres, on retire Aucun
    if len(secu_choices) > 1 and 0 in secu_choices:
        secu_choices = [x for x in secu_choices if x != 0]
    secu1 = secu_choices[0] if secu_choices else 0

    st.markdown(field_label("compass", "Motif du déplacement", required=True), unsafe_allow_html=True)
    trajet = st.selectbox("Motif du déplacement", options=[1,2,3,4,5,9], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Domicile–Travail", 2:"Domicile–École",
            3:"Courses / achats", 4:"Professionnel",
            5:"Promenade / loisirs", 9:"Autre"}[x])

    st.markdown(field_label("age", "Âge", required=True), unsafe_allow_html=True)
    age = st.number_input("Âge", min_value=15, max_value=100, value=35, label_visibility="collapsed")

# ── Valeurs fixes (cachees de l'UI : surface technique, peu impactantes) ─────
# vma + surf viennent maintenant des selectbox dans "Contexte de l'accident".
# circ est recalcule au moment de la prediction selon catr.
# temperature / precipitation / windspeed sont recuperees via Open-Meteo.
int_acc = 1   # Hors intersection
circ = 2      # Bidirectionnelle (recalculee selon catr a la prediction)
vosp = 0      # Sans objet
prof = 1      # Plat
plan = 1      # Rectiligne
infra = 0     # Aucun
situ = 1      # Sur chaussee

# ── DONNÉES TEMPORELLES ───────────────────────────────────────────────────────
st.markdown(section_label("calendar", "Données temporelles"), unsafe_allow_html=True)

MOIS_NOMS = {
    1:"Janvier", 2:"Février", 3:"Mars", 4:"Avril",
    5:"Mai", 6:"Juin", 7:"Juillet", 8:"Août",
    9:"Septembre", 10:"Octobre", 11:"Novembre", 12:"Décembre"
}

c_jour, c_heure, c_mois, c_annee = st.columns(4, gap="large")
with c_jour:
    st.markdown(field_label("calendar", "Jour du mois", required=True), unsafe_allow_html=True)
    jour = st.number_input("Jour", min_value=1, max_value=31, value=15, label_visibility="collapsed")
with c_heure:
    st.markdown(field_label("clock", "Heure de l'accident", required=True), unsafe_allow_html=True)
    heure = st.slider("Heure", min_value=0, max_value=23, value=12,
        label_visibility="collapsed",
        format="%dh00")
    st.markdown(f'<div style="text-align:center;color:#f97316;font-size:1.1rem;font-weight:600;margin-top:-8px;">{heure:02d}h00</div>', unsafe_allow_html=True)
with c_mois:
    st.markdown(field_label("month", "Mois de l'accident", required=True), unsafe_allow_html=True)
    mois = st.selectbox("Mois", options=list(range(1,13)),
        label_visibility="collapsed",
        format_func=lambda x: MOIS_NOMS[x],
        index=5)
with c_annee:
    st.markdown(field_label("calendar", "Année", required=True), unsafe_allow_html=True)
    annee = st.selectbox(
        "Année", options=[2022, 2023, 2024, 2025, 2026],
        index=2,  # default 2024
        label_visibility="collapsed",
    )

# ── LOCALISATION (adresse OU GPS) ─────────────────────────────────────────────
st.markdown(section_label("map-pin", "Localisation (améliore la prédiction via OSRM réel)"), unsafe_allow_html=True)

st.markdown('<div class="mode-loc-radio">', unsafe_allow_html=True)
mode_loc = st.radio(
    "Mode de localisation",
    ["📍 Adresse", "🌐 Coordonnées GPS"],
    horizontal=True,
    label_visibility="collapsed",
    key="mode_loc",
)
st.markdown('</div>', unsafe_allow_html=True)

if mode_loc == "📍 Adresse":
    st.markdown(field_label("map-pin", "Adresse", optional=True), unsafe_allow_html=True)
    c_addr, c_btn = st.columns([4, 1], gap="small", vertical_alignment="bottom")
    with c_addr:
        addr_input = st.text_input(
            "Adresse",
            placeholder="ex: 12 rue de la Paix, 75002 Paris",
            label_visibility="collapsed",
            key="addr_input",
        )
    with c_btn:
        do_geocode = st.button("🔍 Localiser", use_container_width=True)

    if do_geocode and addr_input:
        with st.spinner("Géocodage via API Adresse (data.gouv.fr)..."):
            r = geocode_ban(addr_input)
        if r:
            st.session_state.geo_lat = r["lat"]
            st.session_state.geo_lon = r["lon"]
            st.session_state.geo_label = r["label"]
            # Inference automatique des champs derives de l'adresse
            agg_auto = _infer_agg(r)
            st.session_state.agg_inferred = agg_auto
            st.session_state.vma_inferred = _infer_vma(agg_auto, 3)  # default catr=departementale
            agg_txt = "🏙️ En agglomération" if agg_auto == 2 else "🌾 Hors agglomération"
            st.success(
                f"✅ {r['label']}  →  ({r['lat']:.4f}, {r['lon']:.4f})\n\n"
                f"**Auto-detection** : {agg_txt} (type BAN : `{r['type']}`)"
            )
        else:
            st.error("Adresse introuvable. Essayez d'être plus précis ou passez en mode GPS.")

    if st.session_state.geo_label:
        st.caption(f"📍 {st.session_state.geo_label}")
    lat_input = st.session_state.geo_lat
    lon_input = st.session_state.geo_lon

else:
    c_lat, c_lon = st.columns(2, gap="large")
    with c_lat:
        st.markdown(field_label("compass", "Latitude"), unsafe_allow_html=True)
        lat_input = st.number_input(
            "Latitude", min_value=41.0, max_value=51.5,
            value=st.session_state.geo_lat, step=0.01, format="%.4f",
            label_visibility="collapsed", key="lat_gps",
        )
    with c_lon:
        st.markdown(field_label("compass", "Longitude"), unsafe_allow_html=True)
        lon_input = st.number_input(
            "Longitude", min_value=-5.5, max_value=9.5,
            value=st.session_state.geo_lon, step=0.01, format="%.4f",
            label_visibility="collapsed", key="lon_gps",
        )
    st.session_state.geo_lat = lat_input
    st.session_state.geo_lon = lon_input

st.divider()

# ── BOUTON ────────────────────────────────────────────────────────────────────
_, btn_col = st.columns([4, 1])
with btn_col:
    predict = st.button("Prédire la gravité")

# ── RÉSULTAT ──────────────────────────────────────────────────────────────────
if predict:
    # Localisation explicite ? (geocodage reussi en mode Adresse OU mode GPS)
    location_explicit = (mode_loc == "🌐 Coordonnées GPS") or bool(st.session_state.geo_label)

    # ETAPE 1 : Calcul OSRM (uniquement si localisation explicite)
    routes_info, best_centre, top_centres = None, None, None
    nearest_sau = 15.0
    nearest_pomp = 15.0

    if location_explicit and lat_input and lon_input:
        with st.spinner("Calcul des temps d'intervention (OSRM)..."):
            routes_info, best_centre, top_centres = compute_nearest_centres(lat_input, lon_input, n_per_type=1)
        if best_centre:
            temps_interv = best_centre["duration_min"]
            sau_routes = [r for r in routes_info if r["type"] == "urgences_sau"]
            pomp_routes = [r for r in routes_info if r["type"] == "pompiers"]
            nearest_sau = sau_routes[0]["duration_min"] if sau_routes else temps_interv
            nearest_pomp = pomp_routes[0]["duration_min"] if pomp_routes else temps_interv
    else:
        st.info(
            "ℹ️ Sans adresse ni coordonnées GPS, les temps d'intervention OSRM "
            "ne seront pas calculés et la météo locale ne sera pas récupérée. "
            "La prédiction se basera sur des valeurs neutres."
        )

    # ETAPE 1b : Meteo auto via Open-Meteo (uniquement si localisation explicite)
    if location_explicit and lat_input and lon_input:
        with st.spinner("Récupération des conditions météo..."):
            temperature, precipitation, windspeed = get_weather_from_openmeteo(
                lat_input, lon_input, jour, mois, annee,
            )
        st.markdown(
            f'<div class="meteo-card">'
            f'{ICONS["cloud"]} '
            f'Météo récupérée automatiquement : '
            f'<strong>{temperature:.1f}°C</strong>, '
            f'<strong>{precipitation:.1f} mm</strong>, '
            f'<strong>{windspeed:.0f} km/h</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        # fallback neutre, pas de carte affichee
        temperature, precipitation, windspeed = 15.0, 0.0, 10.0

    # ETAPE 1c : circ auto-deduit depuis la categorie de route
    # autoroute -> chaussees separees (3) ; sinon -> bidirectionnelle (2)
    circ = 3 if catr == 1 else 2

    # ETAPE 2 : Prediction avec les vrais temps OSRM (passes au modele V3)
    payload = {
        "lum": lum, "agg": agg, "int_": int_acc, "atm": atm,
        "col": col_acc, "catr": catr, "circ": circ, "vosp": vosp,
        "prof": prof, "plan": plan, "surf": surf, "infra": infra,
        "situ": situ, "vma": vma, "catu": catu, "sexe": sexe,
        "trajet": trajet, "secu1": secu1, "catv": catv,
        "age": age, "heure": heure, "mois": mois, "jour": jour,
        "temperature": temperature, "precipitation": precipitation,
        "windspeed": windspeed,
        "lat": lat_input, "lon": lon_input,
        # V3 : on envoie les temps OSRM reels deja calcules,
        # pour que l'API les utilise comme features (sinon fallback Haversine).
        "nearest_pompiers_min": nearest_pomp,
        "nearest_sau_min": nearest_sau,
    }
    response = None
    try:
        response = requests.post(
            f"{API_URL}/predict",
            json=payload,
            headers=api_headers(),
            timeout=10,
        )
    except requests.exceptions.Timeout:
        st.error("⏱️ Le serveur met trop de temps à répondre. Veuillez réessayer dans un instant.")
    except requests.exceptions.ConnectionError:
        st.error("🔌 Impossible de joindre l'API. Vérifiez que le serveur est lancé puis réessayez.")
    except Exception as e:
        st.error(f"❌ Erreur inattendue lors de l'appel à l'API. Détail technique : {e}")

    if response is not None:
        if response.status_code == 401:
            st.error("🔐 Votre session a expiré. Veuillez vous reconnecter via la sidebar.")
        elif response.status_code == 422:
            st.error("⚠️ Données du formulaire invalides. Vérifiez les bornes des champs (âge, vitesse, etc.).")
        elif response.status_code >= 500:
            st.error("🛠️ Le serveur est indisponible. Veuillez réessayer dans quelques instants.")
        elif response.status_code != 200:
            st.error(
                f"⚠️ Erreur inattendue de l'API (code {response.status_code}). "
                "Veuillez réessayer ou contacter le support."
            )
        else:
            result = response.json()

            # Stocker dans session_state pour persistance
            st.session_state.last_result = result
            st.session_state.last_routes = routes_info
            st.session_state.last_best = best_centre
            st.session_state.last_coords = (lat_input, lon_input)

            # ETAPE 3 : Affichage resultat
            if result["label"] == "Grave":
                st.error(f"Accident **GRAVE** predit -- Probabilite : **{result['probability']}%**")
            else:
                st.success(f"Accident **PAS GRAVE** predit -- Probabilite : **{result['probability']}%**")

            if st.session_state.jwt_token:
                st.caption("Prediction sauvegardee dans votre historique.")
            else:
                st.caption("Connectez-vous pour sauvegarder vos predictions.")

# ── CARTE PERSISTANTE (affichee tant qu'un resultat existe) ──────
if st.session_state.last_result and st.session_state.last_routes and st.session_state.last_coords:
    result = st.session_state.last_result
    routes_info = st.session_state.last_routes
    best_centre = st.session_state.last_best
    lat_map, lon_map = st.session_state.last_coords

    # Metriques intervention detaillees
    if best_centre:
        # Trouver le temps pompiers (le plus proche parmi les routes)
        pomp_routes = [r for r in routes_info if r.get("type") == "pompiers"]
        sau_routes = [r for r in routes_info if r.get("type") == "urgences_sau"]

        t_pompiers = pomp_routes[0]["duration_min"] if pomp_routes else best_centre["duration_min"]
        t_sau = sau_routes[0]["duration_min"] if sau_routes else best_centre["duration_min"]
        t_total = round(t_pompiers + t_sau, 1)

        # Categorie de risque (basee sur le chi2 golden hour)
        if t_total < 5:
            risque_label = "Intervention rapide"
            risque_color = "#22c55e"
            risque_taux = "~10% deces"
        elif t_total < 15:
            risque_label = "Intervention normale"
            risque_color = "#eab308"
            risque_taux = "~14% deces"
        elif t_total <= 30:
            risque_label = "Intervention lente"
            risque_color = "#f97316"
            risque_taux = "~16.5% deces"
        else:
            risque_label = "Zone blanche"
            risque_color = "#dc2626"
            risque_taux = "~17.4% deces"

        st.markdown(f"""
        <div style="background:rgba(15,23,42,0.8);border:1px solid #334155;border-radius:12px;padding:16px;margin:8px 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div>
                    <div style="color:#94a3b8;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;">Pompiers → Accident</div>
                    <div style="color:#f97316;font-size:1.4rem;font-weight:700;">{t_pompiers} min</div>
                </div>
                <div style="color:#475569;font-size:1.5rem;">→</div>
                <div>
                    <div style="color:#94a3b8;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;">Accident → SAU</div>
                    <div style="color:#3b82f6;font-size:1.4rem;font-weight:700;">{t_sau} min</div>
                </div>
                <div style="color:#475569;font-size:1.5rem;">=</div>
                <div>
                    <div style="color:#94a3b8;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;">Total prise en charge</div>
                    <div style="color:#e2e8f0;font-size:1.4rem;font-weight:700;">{t_total} min</div>
                </div>
                <div style="background:{risque_color};color:white;padding:6px 14px;border-radius:6px;font-weight:700;font-size:0.85rem;">
                    {risque_label}<br/><span style="font-weight:400;font-size:0.7rem;">{risque_taux}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    accident_color = "#dc2626" if result["label"] == "Grave" else "#22c55e"
    m = folium.Map(location=[lat_map, lon_map], zoom_start=12, tiles="CartoDB positron")

    # Heatmap des zones blanches OSRM (>30 min) -- toggleable via le LayerControl
    zb_df = load_zones_blanches()
    if zb_df is not None and len(zb_df):
        zb_layer = folium.FeatureGroup(
            name=f"⚠️ Zones blanches OSRM > 30 min ({len(zb_df):,} accidents historiques)",
            show=False,
        )
        HeatMap(
            zb_df[["lat", "long"]].values.tolist(),
            radius=14, blur=22, min_opacity=0.35,
            gradient={0.0: "#fbbf24", 0.5: "#f97316", 1.0: "#dc2626"},
        ).add_to(zb_layer)
        zb_layer.add_to(m)

    folium.Marker(
        [lat_map, lon_map],
        popup=f"<b>Accident</b><br/>{result['label']}<br/>Probabilite: {result['probability']}%",
        icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
    ).add_to(m)

    folium.Circle(
        [lat_map, lon_map], radius=500,
        color=accident_color, fill=True, fill_opacity=0.15,
    ).add_to(m)

    # Identifier les meilleures routes par categorie pour la mise en avant
    pomp_routes = [r for r in routes_info if r["type"] == "pompiers"]
    sau_routes = [r for r in routes_info if r["type"] == "urgences_sau"]
    best_pomp_nom = min(pomp_routes, key=lambda r: r["duration_min"])["nom"] if pomp_routes else None
    best_sau_nom = min(sau_routes, key=lambda r: r["duration_min"])["nom"] if sau_routes else None

    for route in routes_info:
        is_pomp = route["type"] == "pompiers"
        is_best = route["nom"] in (best_pomp_nom, best_sau_nom)

        # Couleurs distinctes : pompiers = orange, SAU = bleu
        if is_pomp:
            line_color = "#f97316"
            tooltip_lbl = f"🚒 {route['nom']}"
            arrow_label = f"🚒 Pompier &rarr; accident ({route['duration_min']} min)"
        else:
            line_color = "#1e40af"
            tooltip_lbl = f"🏥 {route['nom']}"
            arrow_label = f"🏥 Accident &rarr; SAU ({route['duration_min']} min)"

        weight = 6 if is_best else 3
        opacity = 0.9 if is_best else 0.45
        delay = 600 if is_best else 1200

        # CircleMarker (rendu garanti, pas de dependance Font Awesome)
        folium.CircleMarker(
            [route["lat"], route["lon"]],
            radius=11 if is_best else 7,
            color="#ffffff",
            weight=3,
            fill=True,
            fillColor=line_color,
            fillOpacity=1.0,
            popup=f"<b>{route['nom'][:40]}</b><br/>{route['distance_km']} km | {route['duration_min']} min",
            tooltip=tooltip_lbl,
        ).add_to(m)

        if route.get("geometry"):
            # geometry est dans le sens src -> dst : pompier vers accident OU accident vers SAU
            route_latlon = [[p[1], p[0]] for p in route["geometry"]]
            AntPath(
                route_latlon,
                color=line_color,
                weight=weight,
                opacity=opacity,
                delay=delay,
                dash_array=[10, 20],
                pulse_color="#fff",
                popup=arrow_label,
            ).add_to(m)
        else:
            # Fallback : ligne droite (coords selon direction)
            if is_pomp:
                pts = [[route["lat"], route["lon"]], [lat_map, lon_map]]
            else:
                pts = [[lat_map, lon_map], [route["lat"], route["lon"]]]
            folium.PolyLine(
                pts, color=line_color, weight=weight, opacity=opacity,
                dash_array="8 6", popup=arrow_label,
            ).add_to(m)

    legend_html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:rgba(10,14,26,0.9);
        padding:12px 16px;border-radius:8px;border:1px solid #334155;font-size:12px;color:#e2e8f0;">
        <b style="color:#f97316;">Prediction : {result['label']} ({result['probability']}%)</b><br/>
        <span style="color:#dc2626;">&#9679;</span> Lieu de l'accident<br/>
        <span style="color:#f97316;">&#9679;</span> 🚒 Caserne pompier (intervention)<br/>
        <span style="color:#1e40af;">&#9679;</span> 🏥 SAU / CHU (évacuation)<br/>
        <span style="color:#fbbf24;">&#9679;</span> Zones blanches OSRM (toggle &nearr;)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(position="topright", collapsed=True).add_to(m)

    st.markdown("### Carte d'intervention")
    st_folium(m, width=None, height=500, returned_objects=[])

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR : AUTH + NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.8rem;letter-spacing:3px;
            color:#f97316;">ROUTEZONE</div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.jwt_token:
        st.markdown(
            f'<div class="connected-card">'
            f'<div class="connected-card-label">Connecté</div>'
            f'<div class="connected-card-email">{st.session_state.user_email}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Historique des predictions", use_container_width=True):
            st.session_state.page = "historique"
        if st.button("Mes donnees RGPD", use_container_width=True):
            st.session_state.page = "rgpd"
        if st.button("Deconnexion", use_container_width=True):
            st.session_state.jwt_token = None
            st.session_state.user_email = None
            st.session_state.user_id = None
            st.session_state.page = "prediction"
            # purge des donnees RGPD eventuellement en cache de session
            for k in ("rgpd_export_data", "rgpd_export_count", "rgpd_delete_confirm"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.markdown("---")
        auth_tab = st.radio("Compte", ["Connexion", "Inscription"], horizontal=True, label_visibility="collapsed")

        if auth_tab == "Connexion":
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Mot de passe", type="password")
                submit = st.form_submit_button("Se connecter", use_container_width=True)
                if submit and email and password:
                    try:
                        r = requests.post(
                            f"{API_URL}/auth/login",
                            json={"email": email, "password": password},
                            timeout=10
                        )
                        if r.status_code == 200:
                            data = r.json()
                            st.session_state.jwt_token = data["access_token"]
                            st.session_state.user_email = data["email"]
                            st.session_state.user_id = data["user_id"]
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "Erreur de connexion"))
                    except Exception as e:
                        st.error(f"API inaccessible : {e}")

        else:  # Inscription
            with st.form("register_form"):
                nom = st.text_input("Nom (optionnel)")
                email = st.text_input("Email")
                password = st.text_input("Mot de passe", type="password")
                password2 = st.text_input("Confirmer le mot de passe", type="password")
                submit = st.form_submit_button("Creer un compte", use_container_width=True)
                if submit:
                    if not email or not password:
                        st.error("Email et mot de passe requis")
                    elif password != password2:
                        st.error("Les mots de passe ne correspondent pas")
                    elif len(password) < 6:
                        st.error("Le mot de passe doit faire au moins 6 caracteres")
                    else:
                        try:
                            r = requests.post(
                                f"{API_URL}/auth/register",
                                json={"email": email, "password": password, "nom": nom or None},
                                timeout=10
                            )
                            if r.status_code == 200:
                                data = r.json()
                                st.session_state.jwt_token = data["access_token"]
                                st.session_state.user_email = data["email"]
                                st.session_state.user_id = data["user_id"]
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Erreur d'inscription"))
                        except Exception as e:
                            st.error(f"API inaccessible : {e}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE HISTORIQUE
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "historique" and st.session_state.jwt_token:
    st.markdown("---")
    st.subheader("Historique de vos predictions")

    try:
        r = requests.get(
            f"{API_URL}/predictions?limit=100",
            headers=api_headers(),
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            preds = data.get("predictions", [])
            if preds:
                rows = []
                for p in preds:
                    rows.append({
                        "Date": p["date"][:16] if p["date"] else "",
                        "Label": p["label"],
                        "Probabilite (%)": p["probability"],
                        "Age": p["inputs"]["age"],
                        "Heure": p["inputs"]["heure"],
                        "VMA": p["inputs"]["vma"],
                        "Modele": p["model_version"],
                    })
                df_hist = pd.DataFrame(rows)

                # Metriques rapides
                c1, c2, c3 = st.columns(3)
                n_grave = sum(1 for p in preds if p["label"] == "Grave")
                c1.metric("Total predictions", len(preds))
                c2.metric("Graves", n_grave)
                c3.metric("Prob. moyenne", f"{sum(p['probability'] for p in preds)/len(preds):.1f}%")

                st.dataframe(df_hist, use_container_width=True, hide_index=True)
            else:
                st.info("Aucune prediction sauvegardee. Lancez une prediction pour commencer.")
        else:
            st.error("Erreur lors du chargement de l'historique")
    except Exception:
        st.error("API inaccessible")

    if st.button("Retour aux predictions"):
        st.session_state.page = "prediction"
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE RGPD : export + suppression des predictions de l'utilisateur connecte
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "rgpd" and st.session_state.jwt_token:
    st.markdown("---")
    st.subheader("Mes donnees personnelles (RGPD)")

    st.markdown("""
Conformement au **Reglement General sur la Protection des Donnees** :

- **Article 15 (droit d'acces)** et **article 20 (portabilite)** : vous pouvez
  exporter toutes vos predictions au format JSON.
- **Article 17 (droit a l'oubli)** : vous pouvez demander la suppression
  definitive de toutes vos predictions enregistrees.
""")

    col_export, col_delete = st.columns(2)

    # ── Export ─────────────────────────────────────────────────────
    with col_export:
        st.markdown("#### Exporter mes predictions")
        if st.button("Recuperer mes donnees", use_container_width=True, key="rgpd_export_btn"):
            try:
                r = requests.get(
                    f"{API_URL}/me/predictions/export",
                    headers=api_headers(),
                    timeout=15,
                )
                if r.status_code == 200:
                    payload = r.json()
                    # accepte {"predictions": [...]} ou liste brute
                    preds = payload.get("predictions", payload) if isinstance(payload, dict) else payload
                    nb = len(preds) if isinstance(preds, list) else 0
                    st.session_state["rgpd_export_data"] = payload
                    st.session_state["rgpd_export_count"] = nb
                    st.success(f"{nb} prediction(s) recuperee(s).")
                elif r.status_code == 401:
                    st.error("Session expiree. Reconnectez-vous.")
                else:
                    st.error(f"Erreur API ({r.status_code}) : {r.text[:200]}")
            except Exception as e:
                st.error(f"API inaccessible : {e}")

        if "rgpd_export_data" in st.session_state:
            st.caption(f"{st.session_state.get('rgpd_export_count', 0)} prediction(s) prete(s) au telechargement.")
            st.download_button(
                "Telecharger en JSON",
                data=json.dumps(st.session_state["rgpd_export_data"], indent=2, ensure_ascii=False),
                file_name=f"routezone_predictions_{st.session_state.user_email}.json",
                mime="application/json",
                use_container_width=True,
                key="rgpd_export_download",
            )

    # ── Suppression ────────────────────────────────────────────────
    with col_delete:
        st.markdown("#### Supprimer toutes mes predictions")
        st.markdown("Action **irreversible**. Vos predictions ne seront plus disponibles.")
        confirm = st.checkbox("Je confirme vouloir supprimer mes donnees", key="rgpd_delete_confirm")
        if st.button(
            "Supprimer definitivement",
            use_container_width=True,
            disabled=not confirm,
            key="rgpd_delete_btn",
        ):
            try:
                r = requests.delete(
                    f"{API_URL}/me/predictions",
                    headers=api_headers(),
                    timeout=10,
                )
                if r.status_code == 200:
                    payload = r.json() if r.text else {}
                    n = payload.get("deleted", payload.get("count", 0))
                    st.success(f"{n} prediction(s) supprimee(s).")
                    # purge le cache export de session
                    for k in ("rgpd_export_data", "rgpd_export_count"):
                        st.session_state.pop(k, None)
                elif r.status_code == 401:
                    st.error("Session expiree. Reconnectez-vous.")
                else:
                    st.error(f"Erreur API ({r.status_code}) : {r.text[:200]}")
            except Exception as e:
                st.error(f"API inaccessible : {e}")

    if st.button("Retour aux predictions", key="rgpd_back_btn"):
        st.session_state.page = "prediction"
        st.rerun()

# Footer
st.markdown(
    '<div class="footer">RouteZone &nbsp;--&nbsp; Abdelouahed Meriem &nbsp;--&nbsp; IA Simplon x Microsoft &nbsp;--&nbsp; RNCP37827</div>',
    unsafe_allow_html=True
)

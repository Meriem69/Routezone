import streamlit as st
import requests
from pathlib import Path
import base64

st.set_page_config(
    page_title="RouteZone — Prédiction de gravité",
    page_icon="🚦",
    layout="wide"
)

# ── Image hero ────────────────────────────────────────────────────────────────
HERO_IMAGE = Path(__file__).parent / "anthony-maw-XcjVef6uvYA-unsplash.jpg"
if HERO_IMAGE.exists():
    with open(HERO_IMAGE, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    hero_css = f"background-image: linear-gradient(to bottom, rgba(10,14,26,0.45) 0%, rgba(10,14,26,0.82) 65%, #0a0e1a 100%), url('data:image/jpeg;base64,{img_b64}');"
else:
    hero_css = "background: linear-gradient(135deg, #1a0808 0%, #0a0e1a 100%);"

# ── SVG icons ─────────────────────────────────────────────────────────────────
def svg(path_d, extra="", w=14, h=14, color="#94a3b8", viewBox="0 0 24 24"):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{viewBox}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{path_d}{extra}</svg>'

ICONS = {
    "traffic":  '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><circle cx="12" cy="7" r="2" fill="#ef4444" stroke="none"/><circle cx="12" cy="12" r="2" fill="#f59e0b" stroke="none"/><circle cx="12" cy="17" r="2" fill="#22c55e" stroke="none"/></svg>',
    "warning":  svg('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>', color="#f97316", w=15, h=15),
    "person":   svg('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>', color="#f97316", w=15, h=15),
    "calendar": svg('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>', color="#f97316", w=15, h=15),
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
}

def section_label(key, text):
    return f'<div class="section-label">{ICONS[key]}{text}</div>'

def field_label(key, text):
    return f'<div class="field-label">{ICONS[key]}<span>{text}</span></div>'

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
.hide-label label {{ display: none !important; }}
label, .stSelectbox label, .stNumberInput label {{
    color: #94a3b8 !important;
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
}}
.stSelectbox > div > div {{
    background-color: #111827 !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}}
.stSelectbox > div > div:hover {{ border-color: #f97316 !important; }}
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
}}
hr {{
    border: none !important;
    border-top: 1px solid #1e293b !important;
    margin: 1.5rem 0 !important;
}}
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
    box-shadow: 0 4px 24px rgba(249,115,22,0.38) !important;
}}
div[data-testid="stAlert"] {{
    border-radius: 12px !important;
    font-weight: 500 !important;
    font-size: 1rem !important;
    margin-top: 1rem !important;
}}
.footer {{
    text-align: center;
    color: #e2e8f0;
    font-size: 0.75rem;
    letter-spacing: 1.5px;
    padding: 1rem 0 0.5rem;
    opacity: 0.7;
}}
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
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(section_label("warning", "Contexte de l'accident"), unsafe_allow_html=True)

    st.markdown(field_label("sun", "Luminosité"), unsafe_allow_html=True)
    lum = st.selectbox("Luminosité", options=[1,2,3,4,5], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Plein jour", 2:"Crépuscule / aube",
            3:"Nuit sans éclairage", 4:"Nuit — éclairage non allumé",
            5:"Nuit — éclairage allumé"}[x])

    st.markdown(field_label("map-pin", "Localisation"), unsafe_allow_html=True)
    agg = st.selectbox("Localisation", options=[1,2], label_visibility="collapsed",
        format_func=lambda x: {1:"Hors agglomération", 2:"En agglomération"}[x])

    st.markdown(field_label("cloud", "Conditions météo"), unsafe_allow_html=True)
    atm = st.selectbox("Conditions météo", options=[1,2,3,4,5,6,7,8], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Normale", 2:"Pluie légère", 3:"Pluie forte",
            4:"Neige / grêle", 5:"Brouillard", 6:"Vent fort",
            7:"Temps éblouissant", 8:"Temps couvert"}[x])

    st.markdown(field_label("zap", "Type de collision"), unsafe_allow_html=True)
    col_acc = st.selectbox("Type de collision", options=[1,2,3,4,5,6,7], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Frontale (2 véh.)", 2:"Par l'arrière (2 véh.)",
            3:"Par le côté (2 véh.)", 4:"En chaîne (3 véh.)",
            5:"Multiples (3 véh.)", 6:"Autre", 7:"Sans collision"}[x])

    st.markdown(field_label("road", "Catégorie de route"), unsafe_allow_html=True)
    catr = st.selectbox("Catégorie de route", options=[1,2,3,4,5,6,7], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Autoroute", 2:"Route nationale", 3:"Route départementale",
            4:"Voie communale", 5:"Hors réseau public",
            6:"Parc de stationnement", 7:"Route métropole urbaine"}[x])

with col2:
    st.markdown(section_label("person", "Profil de l'usager"), unsafe_allow_html=True)

    st.markdown(field_label("user", "Catégorie d'usager"), unsafe_allow_html=True)
    catu = st.selectbox("Catégorie d'usager", options=[1,2,3,4], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Conducteur", 2:"Passager",
            3:"Piéton", 4:"Piéton en roller / trottinette"}[x])

    st.markdown(field_label("users", "Sexe"), unsafe_allow_html=True)
    sexe = st.selectbox("Sexe", options=[1,2], label_visibility="collapsed",
        format_func=lambda x: {1:"Masculin", 2:"Féminin"}[x])

    st.markdown(field_label("car", "Catégorie de véhicule"), unsafe_allow_html=True)
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

    st.markdown(field_label("shield", "Équipement de sécurité"), unsafe_allow_html=True)
    secu_choices = st.multiselect("Équipement de sécurité",
        options=[0,1,2,3,4,5,6,7,9],
        default=[0],
        label_visibility="collapsed",
        format_func=lambda x: {
            0:"Aucun", 1:"Ceinture", 2:"Casque",
            3:"Siège enfant", 4:"Gilet réfléchissant",
            5:"Airbag moto", 6:"Gants moto",
            7:"Gants + Airbag moto", 9:"Autre"}[x])
    if len(secu_choices) > 1 and 0 in secu_choices:
        secu_choices = [x for x in secu_choices if x != 0]
    secu1 = secu_choices[0] if secu_choices else 0

    st.markdown(field_label("compass", "Motif du déplacement"), unsafe_allow_html=True)
    trajet = st.selectbox("Motif du déplacement", options=[1,2,3,4,5,9], label_visibility="collapsed",
        format_func=lambda x: {
            1:"Domicile–Travail", 2:"Domicile–École",
            3:"Courses / achats", 4:"Professionnel",
            5:"Promenade / loisirs", 9:"Autre"}[x])

    st.markdown(field_label("age", "Âge"), unsafe_allow_html=True)
    age = st.number_input("Âge", min_value=15, max_value=100, value=35, label_visibility="collapsed")

# Valeurs par défaut
int_acc = 1; circ = 1; vosp = 0; prof = 1; plan = 1
surf = 1; infra = 0; situ = 1; vma = 50
temperature = 15.0; precipitation = 0.0; windspeed = 10.0

# ── DONNÉES TEMPORELLES ───────────────────────────────────────────────────────
st.markdown(section_label("calendar", "Données temporelles"), unsafe_allow_html=True)

MOIS_NOMS = {
    1:"Janvier", 2:"Février", 3:"Mars", 4:"Avril",
    5:"Mai", 6:"Juin", 7:"Juillet", 8:"Août",
    9:"Septembre", 10:"Octobre", 11:"Novembre", 12:"Décembre"
}

c_heure, c_mois = st.columns(2, gap="large")
with c_heure:
    st.markdown(field_label("clock", "Heure de l'accident"), unsafe_allow_html=True)
    heure = st.slider("Heure", min_value=0, max_value=23, value=12,
        label_visibility="collapsed", format="%dh00")
    st.markdown(f'<div style="text-align:center;color:#f97316;font-size:1.1rem;font-weight:600;margin-top:-8px;">{heure:02d}h00</div>', unsafe_allow_html=True)
with c_mois:
    st.markdown(field_label("month", "Mois de l'accident"), unsafe_allow_html=True)
    mois = st.selectbox("Mois", options=list(range(1,13)),
        label_visibility="collapsed",
        format_func=lambda x: MOIS_NOMS[x],
        index=5)

st.divider()

# ── BOUTON ────────────────────────────────────────────────────────────────────
_, btn_col = st.columns([4, 1])
with btn_col:
    predict = st.button("Prédire la gravité")

# ── RÉSULTAT ──────────────────────────────────────────────────────────────────
if predict:
    payload = {
        "lum": lum, "agg": agg, "int_": int_acc, "atm": atm,
        "col": col_acc, "catr": catr, "circ": circ, "vosp": vosp,
        "prof": prof, "plan": plan, "surf": surf, "infra": infra,
        "situ": situ, "vma": vma, "catu": catu, "sexe": sexe,
        "trajet": trajet, "secu1": secu1, "catv": catv,
        "age": age, "heure": heure, "mois": mois,
        "temperature": temperature, "precipitation": precipitation,
        "windspeed": windspeed
    }
    try:
        response = requests.post(
            "http://127.0.0.1:8001/predict",
            json=payload,
            headers={"X-API-Key": "routezone-secret-2024"}
        )
        result = response.json()
        if result["label"] == "Grave":
            st.error(f"Accident GRAVE predit — Probabilite : **{result['probability']}%**")
        else:
            st.success(f"Accident PAS GRAVE predit — Probabilite : **{result['probability']}%**")
    except Exception as e:
        st.warning(f"Impossible de contacter l'API. Verifiez que la FastAPI tourne sur le port 8001. Erreur : {e}")

st.divider()

st.markdown(
    '<div class="footer">RouteZone &nbsp;—&nbsp; Abdelouahed Meriem &nbsp;—&nbsp; IA Simplon × Microsoft &nbsp;—&nbsp; RNCP37827</div>',
    unsafe_allow_html=True
)
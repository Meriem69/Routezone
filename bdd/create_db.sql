-- RouteZone — Schéma PostgreSQL
-- Exécuté automatiquement au démarrage du conteneur via docker-entrypoint-initdb.d

-- TABLE : accidents
CREATE TABLE IF NOT EXISTS accidents (
    num_acc     TEXT    PRIMARY KEY,
    jour        INTEGER NOT NULL,
    mois        INTEGER NOT NULL,
    an          INTEGER NOT NULL,
    heure       INTEGER,
    minute      INTEGER,
    lum         INTEGER,
    agg         INTEGER,
    intersec    INTEGER,
    atm         INTEGER,
    col         INTEGER,
    lat         DOUBLE PRECISION,
    long        DOUBLE PRECISION,
    dep         TEXT
);

-- TABLE : lieux
CREATE TABLE IF NOT EXISTS lieux (
    num_acc     TEXT    PRIMARY KEY,
    catr        INTEGER,
    circ        INTEGER,
    nbv         INTEGER,
    vosp        INTEGER,
    prof        INTEGER,
    plan        INTEGER,
    larrout     DOUBLE PRECISION,
    surf        INTEGER,
    infra       INTEGER,
    situ        INTEGER,
    vma         INTEGER,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc)
);

-- TABLE : vehicules
CREATE TABLE IF NOT EXISTS vehicules (
    id_vehicule INTEGER PRIMARY KEY,
    num_acc     TEXT    NOT NULL,
    senc        INTEGER,
    catv        INTEGER,
    obs         INTEGER,
    obsm        INTEGER,
    choc        INTEGER,
    manv        INTEGER,
    motor       INTEGER,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc)
);

-- TABLE : usagers
CREATE TABLE IF NOT EXISTS usagers (
    id_usager   INTEGER PRIMARY KEY,
    num_acc     TEXT    NOT NULL,
    id_vehicule INTEGER,
    place       INTEGER,
    catu        INTEGER,
    grav        INTEGER NOT NULL,
    sexe        INTEGER,
    an_nais     INTEGER,
    trajet      INTEGER,
    secu1       INTEGER,
    locp        INTEGER,
    actp        INTEGER,
    etatp       INTEGER,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc),
    FOREIGN KEY (id_vehicule) REFERENCES vehicules(id_vehicule)
);

-- TABLE : meteo
CREATE TABLE IF NOT EXISTS meteo (
    id_meteo        SERIAL PRIMARY KEY,
    num_acc         TEXT    NOT NULL UNIQUE,
    temperature     DOUBLE PRECISION,
    precipitation   DOUBLE PRECISION,
    windspeed       DOUBLE PRECISION,
    weathercode     INTEGER,
    source_api      TEXT DEFAULT 'open-meteo',
    date_collecte   TEXT,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc)
);

-- TABLE : barometre_onisr
CREATE TABLE IF NOT EXISTS barometre_onisr (
    id              SERIAL PRIMARY KEY,
    titre           TEXT,
    annee           INTEGER,
    mois            INTEGER,
    date_publication TEXT,
    tues_metropole  INTEGER,
    resume          TEXT,
    source          TEXT,
    url             TEXT
);

-- TABLE : temps_intervention (calculé via OSRM)
CREATE TABLE IF NOT EXISTS temps_intervention (
    num_acc                 TEXT PRIMARY KEY,
    nearest_sau_nom         TEXT,
    nearest_sau_km          DOUBLE PRECISION,
    nearest_sau_min         DOUBLE PRECISION,
    nearest_pompiers_nom    TEXT,
    nearest_pompiers_km     DOUBLE PRECISION,
    nearest_pompiers_min    DOUBLE PRECISION,
    temps_intervention_min  DOUBLE PRECISION,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc)
);

-- TABLE : users (authentification JWT)
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    nom             TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- TABLE : predictions (historique)
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW(),
    -- inputs
    lum             INTEGER,
    agg             INTEGER,
    atm             INTEGER,
    col             INTEGER,
    catr            INTEGER,
    vma             INTEGER,
    catu            INTEGER,
    sexe            INTEGER,
    age             INTEGER,
    heure           INTEGER,
    mois            INTEGER,
    jour            INTEGER,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    -- resultats
    prediction      INTEGER,
    label           TEXT,
    probability     DOUBLE PRECISION,
    model_version   TEXT
);

-- INDEX : performances des requêtes API
CREATE INDEX IF NOT EXISTS idx_accidents_dep ON accidents(dep);
CREATE INDEX IF NOT EXISTS idx_accidents_an ON accidents(an);
CREATE INDEX IF NOT EXISTS idx_accidents_dep_an ON accidents(dep, an);
CREATE INDEX IF NOT EXISTS idx_usagers_grav ON usagers(grav);
CREATE INDEX IF NOT EXISTS idx_usagers_num_acc ON usagers(num_acc);
CREATE INDEX IF NOT EXISTS idx_lieux_num_acc ON lieux(num_acc);
CREATE INDEX IF NOT EXISTS idx_vehicules_num_acc ON vehicules(num_acc);
CREATE INDEX IF NOT EXISTS idx_meteo_num_acc ON meteo(num_acc);
CREATE INDEX IF NOT EXISTS idx_temps_interv_num_acc ON temps_intervention(num_acc);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at);

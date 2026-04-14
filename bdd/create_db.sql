PRAGMA foreign_keys = ON;
-- Suppression des tables si elles existent déjà
DROP TABLE IF EXISTS meteo;
DROP TABLE IF EXISTS usagers;
DROP TABLE IF EXISTS vehicules;
DROP TABLE IF EXISTS lieux;
DROP TABLE IF EXISTS accidents;

-- TABLE : accidents
CREATE TABLE accidents (
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
    lat         REAL,
    long        REAL,
    dep         TEXT
);

-- TABLE : lieux
CREATE TABLE lieux (
    num_acc     TEXT    PRIMARY KEY,
    catr        INTEGER,
    circ        INTEGER,
    nbv         INTEGER,
    vosp        INTEGER,
    prof        INTEGER,
    plan        INTEGER,
    larrout     REAL,
    surf        INTEGER,
    infra       INTEGER,
    situ        INTEGER,
    vma         INTEGER,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc)
);

-- TABLE : vehicules
CREATE TABLE vehicules (
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
CREATE TABLE usagers (
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
CREATE TABLE meteo (
    id_meteo        INTEGER PRIMARY KEY AUTOINCREMENT,
    num_acc         TEXT    NOT NULL UNIQUE,
    temperature     REAL,
    precipitation   REAL,
    windspeed       REAL,
    weathercode     INTEGER,
    source_api      TEXT DEFAULT 'open-meteo',
    date_collecte   TEXT,

    FOREIGN KEY (num_acc) REFERENCES accidents(num_acc)
);


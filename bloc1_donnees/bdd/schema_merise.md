# Modélisation Merise — RouteZone / BDD Accidents BAAC

**Projet :** RouteZone — Prédiction de la gravité des accidents routiers  
**Auteure :** Meriem Abdelouahed | Formation Dev IA — Simplon x Microsoft  

---

## 1. Modèle Conceptuel des Données (MCD)

Le MCD décrit les entités métier et leurs relations, indépendamment de toute technologie.

![MCD RouteZone](mcd.png)



### Cardinalités expliquées

- **ACCIDENT → LIEU** : (1,1) — chaque accident a exactement un lieu d'occurrence et un lieu peux avoir aucun ou plusieurs accident (0,n)
- **ACCIDENT → USAGER** : 1,n — un accident implique au minimum 1 usager, potentiellement plusieurs (collision entre véhicules) et un usager est impliqué dans exactement un accident 1,1
- **ACCIDENT → VEHICULE** : (1,n) — au moins 1 véhicule par accident, un véhicule est concerné par exactement un accident (1,1)
- **USAGER → VEHICULE** : (1,1), un usager occupe exactement un véhicule et un véhicule peut avoir un ou plsieurs passagers (1,n)
- **ACCIDENT → METEO** : (0,1) — la météo est enrichie via API mais ne couvre pas 100% des accidents (GPS manquant ou hors plage),une donnée météo correspond à exactement un accident (1,1)

---

## 2. Modèle logique de données (MLD) 

Le MLD (Modèle Logique des Données) est la traduction du MCD en tables relationnelles. Il précise pour chaque table ses attributs, ses clés primaires (identifiants uniques) et ses clés étrangères (liens vers d'autres tables), indépendamment du langage de base de données utilisé.




ACCIDENT : <u>num_acc</u>, jour, mois, an, heure, minute, lum, agg, 
 intersec, atm, col, lat, long, dep


LIEU : <u>*num_acc*</u>, catr, circ, nbv, vosp, prof, plan, 
 larrout, surf, infra, situ, vma


VEHICULE : <u>id_vehicule</u>, *num_acc*, senc, catv, obs, 
 obsm, choc, manv, motor


USAGER : <u>id_usager</u>, *num_acc*, *id_vehicule*, place, catu, grav, 
 sexe, an_nais, trajet, secu1, locp, actp, etatp


METEO : <u>id_meteo</u>, *num_acc*, temperature, precipitation, 
        windspeed, weathercode, source_api, date_collecte


> Clé primaire → soulignée | Clé étrangère → en italique

## 3. Modèle Physique des Données (MPD)

Le MPD traduit le MCD en tables relationnelles avec les types de données, clés primaires et étrangères.

### Table `accidents`

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `num_acc` | TEXT | PRIMARY KEY | Identifiant unique de l'accident (ex: 202200000001) |
| `jour` | INTEGER | NOT NULL | Jour du mois (1-31) |
| `mois` | INTEGER | NOT NULL | Mois (1-12) |
| `an` | INTEGER | NOT NULL | Année (2022, 2023, 2024) |
| `heure` | INTEGER | | Heure extraite de hrmn (0-23) |
| `minute` | INTEGER | | Minute extraite de hrmn (0-59) |
| `lum` | INTEGER | | Luminosité (1=plein jour … 5=nuit sans éclairage) |
| `agg` | INTEGER | | Localisation agglomération (1=hors, 2=en agglomération) |
| `intersec` | INTEGER | | Type d'intersection (renommé depuis 'int' — mot réservé SQL) |
| `atm` | INTEGER | | Conditions atmosphériques déclarées |
| `col` | INTEGER | | Type de collision |
| `lat` | REAL | | Latitude GPS |
| `long` | REAL | | Longitude GPS |
| `dep` | TEXT | | Code département |

### Table `lieux`

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `num_acc` | TEXT | PRIMARY KEY, FOREIGN KEY → accidents | Identifiant de l'accident |
| `catr` | INTEGER | | Catégorie de route (1=autoroute … 9=autre) |
| `circ` | INTEGER | | Régime de circulation |
| `nbv` | INTEGER | | Nombre de voies |
| `vosp` | INTEGER | | Voie réservée (piste cyclable, bus...) |
| `prof` | INTEGER | | Profil de la route (plat, côte, sommet...) |
| `plan` | INTEGER | | Tracé en plan (ligne droite, courbe...) |
| `larrout` | REAL | | Largeur de la chaussée (m) |
| `surf` | INTEGER | | État de la surface (sèche, mouillée, verglacée...) |
| `infra` | INTEGER | | Aménagement infrastructure |
| `situ` | INTEGER | | Situation de l'accident sur la route |
| `vma` | INTEGER | | Vitesse maximale autorisée (km/h) |

### Table `usagers`

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `id_usager` | INTEGER | PRIMARY KEY | Identifiant natif ONISR |
| `num_acc` | TEXT | NOT NULL, FOREIGN KEY → accidents | Accident concerné |
| `id_vehicule` | INTEGER | FOREIGN KEY → vehicules | Véhicule de l'usager |
| `place` | INTEGER | | Place dans le véhicule |
| `catu` | INTEGER | | Catégorie d'usager (1=conducteur, 2=passager, 3=piéton) |
| `grav` | INTEGER | NOT NULL | **Variable cible** — gravité (1=indemne, 2=tué, 3=blessé hosp., 4=blessé léger) |
| `sexe` | INTEGER | | Sexe (1=masculin, 2=féminin) |
| `an_nais` | INTEGER | | Année de naissance |
| `trajet` | INTEGER | | Motif du déplacement |
| `secu1` | INTEGER | | Équipement de sécurité |
| `locp` | INTEGER | | Localisation piéton |
| `actp` | INTEGER | | Action piéton |
| `etatp` | INTEGER | | État piéton |

### Table `vehicules`

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `id_vehicule` | INTEGER | PRIMARY KEY | Identifiant numérique natif ONISR |
| `num_acc` | TEXT | NOT NULL, FOREIGN KEY → accidents | Accident concerné |
| `senc` | INTEGER | | Sens de circulation |
| `catv` | INTEGER | | Catégorie de véhicule (1=bicyclette, 7=VL, 10=VU...) |
| `obs` | INTEGER | | Obstacle fixe heurté |
| `obsm` | INTEGER | | Obstacle mobile heurté |
| `choc` | INTEGER | | Point de choc initial |
| `manv` | INTEGER | | Manœuvre avant accident |
| `motor` | INTEGER | | Type de motorisation |

### Table `meteo`

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `id_meteo` | INTEGER | PRIMARY KEY AUTOINCREMENT | Identifiant technique |
| `num_acc` | TEXT | UNIQUE, FOREIGN KEY → accidents | Accident enrichi |
| `temperature` | REAL | | Température en °C au moment de l'accident |
| `precipitation` | REAL | | Précipitations en mm |
| `windspeed` | REAL | | Vitesse du vent en km/h |
| `weathercode` | INTEGER | | Code météo WMO (0=ciel dégagé, 61=pluie...) |
| `source_api` | TEXT | | Toujours 'open-meteo' — traçabilité |
| `date_collecte` | TEXT | | Date de la requête API (ISO 8601) |

---


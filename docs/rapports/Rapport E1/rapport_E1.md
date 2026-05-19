# RouteZone — Rapport E1

> **Document** : Rapport professionnel — Épreuve E1  
> **Titre** : Collecte, préparation et exposition des données  
> **Auteure** : Meriem Abdelouahed  
> **Formation** : Développeur en Intelligence Artificielle — Simplon × Microsoft  
> **Certification** : RNCP37827  
> **Soutenance** : Juin 2026 (distanciel)  
> **Bloc** : Bloc 1 — Compétences C1 à C5  
> **Sources de données** : BAAC 2022-2024 (data.gouv.fr) · Open-Meteo · ONISR · OSRM · SAU & casernes (data.gouv.fr)

---

## Sommaire

1. [Contexte et objectif](#1-contexte-et-objectif)
2. [Collecte des données](#2-collecte-des-données)
3. [Nettoyage et préparation](#3-nettoyage-et-préparation)
4. [Base de données PostgreSQL](#4-base-de-données-postgresql)
5. [API REST Data — FastAPI](#5-api-rest-data--fastapi)
6. [Conclusion](#6-conclusion)

---

## 1. Contexte et objectif

RouteZone est un système de machine learning visant à prédire la gravité d'un accident routier (Grave : tué ou hospitalisé / Pas grave : indemne ou blessé léger) à partir des données BAAC (Bulletin d'Analyse des Accidents Corporels) 2022-2024, publiées en open data par le Ministère de l'Intérieur.

Le projet répond à une problématique de sécurité routière : aider les autorités et les services de secours à anticiper les cas critiques pour mieux prioriser les interventions. La spécificité de RouteZone réside dans l'intégration du concept de **Golden Hour**, principe médical établi en traumatologie selon lequel la prise en charge d'une victime grave dans les 60 minutes suivant le traumatisme augmente significativement les chances de survie.

### Périmètre du Bloc E1

Le Bloc E1 couvre la collecte, la préparation et l'exposition des données. Il constitue le socle qui alimente l'ensemble du projet.

| Compétence | Action réalisée | Livrable |
|---|---|---|
| **C1 — Automatiser l'extraction** | 12 CSV BAAC + API Open-Meteo + scraping ONISR + enrichissement OSRM | 4 notebooks + 3 scripts `.py` |
| **C2 — Sources fiables** | Identification et validation des sources open data officielles | Documentation README |
| **C3 — Nettoyage / transformation** | Gestion des NaN, des types, des colonnes inutiles, merge des 4 tables | notebook_01 + dataset_clean.csv |
| **C4 — Base de données** | Modélisation Merise (MCD/MPD), PostgreSQL 16, scripts d'import | schema_merise.md + create_db.sql |
| **C5 — API REST Data** | Développement FastAPI 7 endpoints documentés Swagger | src/api/routes_data.py |

---

## 2. Collecte des données

La collecte s'appuie sur quatre sources complémentaires : le jeu de données principal BAAC, deux enrichissements externes (Open-Meteo et ONISR), et un enrichissement calculé via OSRM.

### 2.1 Données BAAC

Les fichiers BAAC sont organisés en 4 tables liées par la clé `Num_Acc` :

- **caract** : caractéristiques de l'accident (date, heure, conditions atmosphériques, localisation)
- **lieux** : caractéristiques du lieu (type de route, vitesse maximale autorisée, état de la surface)
- **usagers** : personnes impliquées (âge, sexe, gravité, équipement de sécurité)
- **vehicules** : véhicules impliqués (catégorie, type de collision)

Au total, 12 fichiers CSV ont été chargés, représentant **153 054 accidents** sur 3 ans (2022-2024), impliquant **413 570 usagers** et environ **270 000 véhicules**. Un accident impliquant plusieurs personnes apparaît une seule fois dans `caract` et `lieux`, mais plusieurs fois dans `usagers` et `vehicules`.

### 2.2 Enrichissement Open-Meteo

La colonne `atm` du BAAC code les conditions météo de façon déclarative et subjective (normale, pluie légère, brouillard, etc.). Cette donnée ne reflète pas nécessairement les conditions réelles au moment de l'accident. L'API Open-Meteo (gratuite, sans clé d'authentification) fournit la météo réelle heure par heure pour chaque coordonnée GPS.

L'enrichissement ajoute 4 variables au dataset :

- `temperature` (en degrés Celsius)
- `precipitation` (en mm)
- `windspeed` (vitesse du vent en km/h)
- `weathercode` (code météo standardisé)

La collecte sur 153 054 accidents s'effectue via une boucle Python avec une pause de 0,1 seconde entre chaque requête pour respecter les limites de l'API. Cet enrichissement objective les conditions météorologiques, ce qui améliore significativement la pertinence des features du modèle.

### 2.3 Scraping ONISR

Le baromètre mensuel ONISR (nombre de tués sur les routes par mois) n'est pas disponible en CSV : il est uniquement publié sur le site web de l'Observatoire National Interministériel de la Sécurité Routière. Le scraping est réalisé avec les bibliothèques `requests` et `BeautifulSoup`.

Lors de l'inspection du HTML du site, j'ai découvert un paramètre d'URL `field_annees_target_id` permettant de cibler directement une année spécifique sans parcourir toutes les pages. Cette optimisation réduit le nombre de requêtes et évite de saturer le serveur. Les données scrapées servent ensuite à valider la qualité du dataset BAAC en comparant les comptages mensuels (test de cohérence externe).

### 2.4 Enrichissement OSRM — Golden Hour

Cette section présente le principal apport méthodologique du projet RouteZone par rapport aux travaux existants sur les données BAAC.

#### Le concept de Golden Hour

Le **Golden Hour** (Heure d'Or) est un principe médical fondamental établi en traumatologie : la prise en charge d'une victime grave dans les 60 minutes suivant le traumatisme augmente significativement les chances de survie. Au-delà de cette fenêtre temporelle, le taux de mortalité progresse de manière significative en raison du choc hémorragique, de l'hypothermie et des complications associées. Ce concept est aujourd'hui un standard de référence dans l'organisation des secours d'urgence.

Le BAAC ne contient **aucune information** sur le temps d'intervention réel des secours. Or, ce facteur est déterminant pour la gravité finale d'un accident. J'ai donc décidé de l'intégrer comme variable explicative.

#### Calcul des temps d'intervention avec OSRM

**OSRM** (Open Source Routing Machine) est un moteur de routage haute performance qui calcule des itinéraires réels sur le réseau routier d'OpenStreetMap. Contrairement à une approximation à vol d'oiseau (formule de Haversine), OSRM tient compte du réseau routier réel, des vitesses limites et de la topologie.

Le pipeline d'enrichissement procède en trois étapes :

- **Téléchargement** des cartes régionales depuis Geofabrik (extraits OpenStreetMap par région française)
- **Préparation** des données OSRM avec l'algorithme MLD (Multi-Level Dijkstra) pour chaque région
- **Calcul** pour chaque accident du temps de trajet depuis la caserne de pompiers la plus proche, puis du temps de trajet vers le Service d'Accueil des Urgences (SAU) le plus proche

Les données externes utilisées pour ce calcul proviennent également d'open data : **5 906 casernes de pompiers** (CIS) et **638 SAU** répertoriés sur data.gouv.fr.

#### Résultats : zones blanches détectées

La comparaison entre l'approximation Haversine (utilisée dans une première version) et le calcul OSRM révèle des résultats marquants. OSRM détecte **47 % de zones blanches supplémentaires** (accidents avec un temps de prise en charge supérieur à 30 minutes) que Haversine ne voyait pas. Concrètement, 16 305 accidents sont identifiés en zone blanche par OSRM, contre 11 102 par Haversine.

La corrélation entre temps d'intervention et taux de décès est statistiquement renforcée : la valeur du test du Chi² passe de **p = 5,8e-20** (Haversine) à **p = 6,6e-27** (OSRM), soit un effet 38 % plus fort. Cette feature OSRM devient le **1er facteur d'importance** dans le modèle final, devant l'âge et la vitesse maximale autorisée.

---

## 3. Nettoyage et préparation

Le nettoyage du dataset s'est effectué en 10 étapes ordonnées sur les tables brutes, avant la fusion finale. La méthodologie suit le principe : nettoyer chaque table indépendamment, puis fusionner, plutôt que l'inverse, afin de limiter la propagation d'erreurs.

### 3.1 Étapes principales

- Correction du nom de colonne `Accident_Id` en `Num_Acc` sur le fichier `caract` 2022 (bug de nommage qui aurait cassé tous les merges)
- Concaténation des 3 années pour chaque table (caract, lieux, usagers, vehicules)
- Remplacement des valeurs `-1` par `NaN` (convention BAAC : -1 signifie « non renseigné »)
- Visualisation des valeurs manquantes avec la bibliothèque `missingno` pour identifier les patterns
- Suppression des 2 doublons stricts détectés dans la table `lieux`
- **Gestion des types** : conversion des colonnes numériques lues comme texte par pandas
- Correction des coordonnées GPS : remplacement de la virgule décimale française par un point, filtrage des DOM-TOM (9 578 lignes retirées pour rester sur la France métropolitaine)
- **Gestion des colonnes inutiles** : suppression de celles ayant plus de 90 % de valeurs manquantes ou sans intérêt pour la modélisation
- **Gestion des NaN** : suppression de la ligne pour les colonnes critiques (`grav`, `sexe`, `dep`), imputation par le mode pour les variables catégorielles, par la médiane pour les variables numériques
- Vérification finale : **0 valeur manquante** restante dans toutes les tables nettoyées

La fusion des 4 tables s'effectue via des `left joins` sur `Num_Acc`. Le dataset final compte 413 570 lignes au niveau usager et 44 colonnes.

Trois variables dérivées ont été créées pour enrichir le pouvoir explicatif du dataset :

- `age` : calculé à partir de l'année de l'accident et de l'année de naissance (`an - an_nais`)
- `heure` : extraite du champ `hrmn` (format HHMM)
- `jour_semaine` : dérivé de la date complète (lundi à dimanche)

### 3.2 Analyses de biais

Deux analyses de biais ont été réalisées pour assurer une lecture critique des données, conformément aux exigences éthiques d'un projet de data science.

**Biais de représentation par sexe** : comparaison entre le volume brut d'accidents par sexe et le taux corrigé rapporté à la population. Les hommes représentent une part majoritaire des accidents corporels, mais cette différence doit être analysée en tenant compte de leur exposition au risque (kilométrage parcouru, professions à risque).

**Biais géographique** : comparaison entre le volume brut d'accidents par département et le taux pour 100 000 habitants. Cette analyse permet de distinguer les départements réellement dangereux des départements simplement peuplés.

Ces analyses illustrent l'importance d'une lecture critique des données brutes : un volume élevé n'est pas synonyme de risque élevé sans normalisation.

---

## 4. Base de données PostgreSQL

La base de données RouteZone est modélisée selon la méthode **Merise** (Modèle Conceptuel de Données puis Modèle Physique de Données) et implémentée en **PostgreSQL 16**.

### 4.1 Choix technologique

PostgreSQL a été choisi pour ses qualités adaptées à un projet de production :

- **Conformité ACID** (Atomicité, Cohérence, Isolation, Durabilité) : garantit l'intégrité des données lors des transactions
- **Support natif du JSON** et des types géospatiaux (utile pour les coordonnées GPS)
- **Gestion de la concurrence** : permet à plusieurs services (API, scripts d'import, monitoring) d'accéder simultanément aux données
- Excellente **intégration avec Docker** et avec l'écosystème Python via SQLAlchemy et psycopg2
- Solution **open source** largement utilisée en production dans l'industrie

### 4.2 Schéma de la base

La base contient **8 tables** organisées en deux groupes fonctionnels :

**Données métier**
- `accidents` : caractéristiques des 153 054 accidents (date, heure, localisation, conditions)
- `lieux` : informations sur le lieu de l'accident (type de route, surface, vitesse)
- `usagers` : 413 570 personnes impliquées (âge, sexe, gravité, équipement)
- `vehicules` : véhicules impliqués (catégorie, type de collision)
- `meteo` : données Open-Meteo enrichies (temperature, precipitation, windspeed)
- `barometre_onisr` : statistiques mensuelles ONISR (nombre de tués par mois)

**Données applicatives**
- `users` : comptes utilisateurs de l'application (email, mot de passe hashé en bcrypt)
- `predictions` : historique des prédictions effectuées par chaque utilisateur (datées, avec probabilité)

### 4.3 Scripts d'alimentation

- `import_data.py` : import des CSV BAAC nettoyés (153 054 accidents importés)
- `collect_meteo.py` : appel API Open-Meteo et insertion en base
- `scraping_onisr.py` : scraping des baromètres mensuels

---

## 5. API REST Data — FastAPI

L'API expose les données collectées via des endpoints REST documentés automatiquement par **Swagger UI**. Cette API est lancée par la commande `python -m uvicorn main:app --reload` et écoute par défaut sur `http://127.0.0.1:8001`.

### 5.1 Architecture

L'API est construite avec **FastAPI** (framework Python moderne basé sur Starlette et Pydantic). Elle intègre :

- Une authentification par clé API (header `X-API-Key`) pour les endpoints de données
- Une authentification JWT (JSON Web Token) pour les endpoints utilisateurs (gestion de session)
- Une validation automatique des données entrantes via Pydantic
- Une documentation interactive sur `/docs` (Swagger) et `/redoc`

### 5.2 Endpoints exposés

| Endpoint | Authentification | Description |
|---|---|---|
| `GET /` | Public | Health check (vérifie que l'API est en ligne) |
| `GET /accidents` | API Key | Liste filtrable par département, année, gravité (max 1000) |
| `GET /accidents/stats` | API Key | Statistiques globales (total, répartition, top départements) |
| `GET /accidents/departement/{dep}` | API Key | Statistiques mensuelles pour un département |
| `GET /accidents/gravite` | API Key | Répartition des usagers par niveau de gravité |
| `GET /meteo/stats` | API Key | Statistiques météo agrégées |
| `GET /onisr/barometre` | API Key | Baromètres mensuels ONISR avec filtre par année |

---

## 6. Conclusion

Le Bloc E1 constitue le socle de données du projet RouteZone. Les livrables produits dans cette phase sont :

- **Dataset nettoyé** : 153 054 accidents, 413 570 usagers, 0 NaN (`dataset_clean.csv`)
- **Dataset enrichi** : ajout de `temperature`, `precipitation`, `windspeed`, `weathercode`, `temps_total_osrm`
- **Base de données PostgreSQL 16** : 8 tables, schéma Merise documenté
- **4 notebooks** documentés (exploration, météo, ONISR, OSRM)
- **4 scripts** de production (`collect_meteo.py`, `scraping_onisr.py`, `import_data.py`, `enrich_osrm_batch.py`)
- **API FastAPI** : 7 endpoints documentés avec Swagger automatique

La spécificité méthodologique de ce bloc — l'intégration du Golden Hour via OSRM — constitue l'apport différenciant par rapport aux approches classiques sur ce dataset. Cette feature dérivée est devenue le facteur le plus discriminant du modèle final, validant l'hypothèse de départ selon laquelle le temps d'intervention des secours est un facteur clé de la gravité finale d'un accident.

Le dataset enrichi et l'API de données alimenteront le **Bloc E3** : entraînement et comparaison de modèles de classification (Random Forest, XGBoost, LightGBM) pour prédire la gravité des accidents, avec MLflow pour le suivi des expériences.

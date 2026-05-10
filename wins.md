# WINS — Meriem RouteZone

## Mai 2026

### 6 mai 2026 (mercredi)
- 3 audits complets du projet (Bloc 1, Bloc 2, Bloc 3) initiés par moi-même
- Repo GitHub à jour : push de 104 fichiers (commit bef39cf)
- 3 corrections de sécurité commit séparément (int_feat, Pydantic, CORS)
- Création d'un venv propre + requirements.txt clean (215 → 31 lignes)
- Détection seule de bugs cachés (formats français BAAC, dates de push)

### 7 mai 2026 (jeudi)
- Réflexe EDA pro : vérification des données avant transformation 
  (départements alphanumériques)
- 2 derniers tests pytest fixés → 19/19 PASSENT
- Tests d'intégration complets : auth + data + IA + BDD
- Question pertinente : "et la BDD a-t-elle bien été mise à jour avec les nouveaux CSV ?" — la VRAIE bonne question
- Compris la vraie utilité de CORS : protège les utilisateurs authentifiés contre les attaques cross-origin via les cookies/JWT. Inutile pour les API publiques sans données perso (tel que l'API météo)
- Maîtrisé l'argument "paradoxe de l'accuracy" : sur un dataset déséquilibré, l'accuracy peut être trompeuse, le Recall sur la classe minoritaire est plus pertinent.

### 9 mai 2026 (samedi)
- projet stable après 2 jours de pause, 19/19 sans modification.
- Compris threshold tuning : seuil de proba qui détermine la classe prédite, à ajuster selon le compromis Recall/Precision adapté au métier.
- Compris les concepts CI/CD : pull request, scheduler, workflow_dispatch, healthcheck Docker, env vars Postgres, IPv4/IPv6.
- Premier workflow GitHub Actions créé et fonctionnel du PREMIER COUP
- Tests RouteZone : 2m 46s, 19/19 passent sur Ubuntu Linux
- BDD recréée from scratch automatiquement à chaque push
- Compris : runners GitHub-hosted, services Docker, healthcheck Postgres,
  variables d'environnement, IPv4 vs IPv6
- Ajouté badge CI au README pour visibilité
-  Compris la stratégie de fallback OSRM → Haversine → défaut, et la définition métier de VMA (Vitesse Maximale Autorisée).
- 29 tests pytest tous verts en local (29.86s)
- Push commit eb01948 sur GitHub
- Mes tests couvrent maintenant :
  * Auth + Endpoints data (12 tests)
  * Endpoints IA (6 tests)
  * Smoke modèle ML (5 tests : version, reproductibilité, proba, label, perf)
  * Bornes Pydantic (5 tests : age, heure, mois, lat, vma)
  * Auth JWT (1 test)
- Compris : importance d'aligner les tests sur le contrat RÉEL de l'API,
  pas sur une spec théorique

### 10 mai 2026 (dimanche) 

- Création du module `src/api/logger.py` (config logger Python : INFO + console + fichier)
- Logger intégré dans `main.py` (démarrage API) et `routes_ia.py` (chaque prédiction)
- Fichier `logs/api.log` se remplit automatiquement à chaque action de l'API
- 29/29 tests pytest passent toujours
- Compris :
  - Logger Python (niveau, handler, format)
  - Différence niveau (filtre) vs handler (destination)
  - Pourquoi on ne push PAS les logs sur Git (sensibles + bruyants)
  - Que mes logs prouvent le déterminisme du modèle
- Commit f4bad3e push sur master


### A revoir : 
-  le docker-compose.yml ligne par ligne (et toutes les commandes Docker du quotidien).
À revoir avant l'oral :
- Docker en détail (commandes + docker-compose ligne par ligne)
- SQL basique (SELECT, INSERT, UPDATE, DELETE, JOIN, GROUP BY, WHERE)
- CI/CD (à venir aujourd'hui)
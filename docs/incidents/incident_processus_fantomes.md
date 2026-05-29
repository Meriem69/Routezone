# Incident — Processus fantômes sur le port 8001

**Date** : 29 mai 2026   
**Composant affecté** : Monitoring (Prometheus \+ Grafana)   
**Statut** : Résolu   
**Auteur** : Meriem Abdelouahed

---

## 1\. Symptôme observé

Le dashboard Grafana RouteZone affiche "Aucune donnée" sur tous les panels, alors que :

- L'API tourne normalement (`docker ps` → `routezone_api` est `healthy`)  
- Les prédictions de test sont bien effectuées (réponse `200 OK`)  
- L'endpoint `/metrics` de l'API expose bien les valeurs (`routezone_predictions_total = 7.0`)  
- La page Prometheus `/targets` indique que la cible est **EN HAUT** (verte), avec un scrape récent (7 ms de latence)

Mais en interrogeant Prometheus directement via `/graph` avec la requête `routezone_predictions_total`, la réponse est : **"Résultat de requête vide"**.

## 2\. Diagnostic

### Étape 1 — Hypothèse Docker corrompu

Premier réflexe : redémarrage propre de tous les containers.

docker-compose down

docker volume rm routezone\_prometheus\_data

docker-compose up \-d

Résultat : le problème persiste.

### Étape 2 — Vérification de la configuration Prometheus

Lecture du fichier `monitoring/prometheus.yml` :

global:

  scrape\_interval: 15s

scrape\_configs:

  \- job\_name: 'routezone\_api'

    static\_configs:

      \- targets: \['host.docker.internal:8001'\]

    metrics\_path: '/metrics'

Aucune erreur de configuration. Le scrape vise bien `host.docker.internal:8001`.

### Étape 3 — Vérification des logs Prometheus

docker logs routezone\_prometheus \--tail 50

Découverte d'une ligne suspecte :  
msg="write block resulted in empty block"

Prometheus tente d'écrire un bloc dans son stockage, mais ce bloc est vide. Cela confirme qu'aucune métrique n'arrive, malgré les scrapes réussis.

### Étape 4 — L'idée déclic : vérification des processus locaux

Hypothèse : Prometheus tape sur la **mauvaise API**. Vérification avec `netstat` :

netstat \-ano | findstr :8001

Résultat :  
TCP    0.0.0.0:8001       LISTENING    9284   (container Docker)  
TCP    127.0.0.1:8001     LISTENING    10336  (processus inconnu)  
TCP    \[::1\]:8001         LISTENING    10420  (processus inconnu)

**Trois processus différents** écoutent sur le port 8001 \! L'API Docker (PID 9284\) coexiste avec deux autres processus Python orphelins (PID 10336 et 10420).

### Étape 5 — Confirmation par comparaison des endpoints

Pour confirmer que Prometheus tapait sur la mauvaise instance :

docker exec routezone\_prometheus wget \-qO- http://host.docker.internal:8001/metrics

**Comparaison clé** :

- Endpoint vu par Prometheus : Python 3.11.9, métriques `routezone_predictions_total` SANS valeur  
- Endpoint vu depuis le navigateur Windows : Python 3.11.14, métriques `routezone_predictions_total = 7.0`

Les deux Python sont de versions différentes : ce sont bien deux instances distinctes de l'API.

## 3\. Cause racine

Les processus fantômes proviennent d'anciennes sessions d'**uvicorn lancées en local** avec l'option `--reload`.

L'option `--reload` redémarre automatiquement le serveur à chaque modification de fichier Python. Quand on ferme un terminal sans utiliser `Ctrl+C` proprement (par exemple en fermant la fenêtre PowerShell directement), le processus enfant uvicorn peut survivre et continuer à écouter sur le port 8001 en arrière-plan.

Quand Prometheus, depuis son container Docker, tente de scrape `host.docker.internal:8001`, Windows redirige cette requête vers `127.0.0.1:8001`. Or, le processus fantôme écoute également sur `127.0.0.1:8001` et répond à Prometheus à la place du container Docker (qui lui écoute sur `0.0.0.0:8001`).

Le processus fantôme étant une ancienne instance d'uvicorn qui n'a jamais reçu aucune prédiction, son endpoint `/metrics` est vide. Prometheus reçoit donc une réponse valide (HTTP 200\) mais sans aucune donnée utile.

## 4\. Résolution

### Tuer les processus fantômes

taskkill /PID 10336 /F

taskkill /PID 10420 /F

Get-Process python3.11 | Stop-Process \-Force

### Vérifier que seul le container Docker reste

netstat \-ano | findstr :8001

Doit afficher uniquement :

TCP    0.0.0.0:8001    LISTENING    9284

TCP    \[::\]:8001       LISTENING    9284

### Relancer du trafic et vérifier Prometheus

Après avoir relancé un script de prédictions, Prometheus a immédiatement commencé à enregistrer les métriques. Le dashboard Grafana s'est rempli correctement : 81 prédictions, bar chart Grave/Pas grave, etc.

## 5\. Leçons apprises

1. **Persévérer face à un bug** : les premières solutions classiques (reset Docker, vérification des configs) n'ont rien donné. Sans persévérance et intuition, j'aurais abandonné.  
     
2. **Connaître ses outils en profondeur** : la commande `netstat -ano` permet d'identifier précisément quel processus écoute sur quel port. C'est cette commande qui a permis de débloquer la situation.  
     
3. **Les processus fantômes existent** : les serveurs lancés en mode `--reload` peuvent survivre à la fermeture de leur terminal et continuer à occuper des ports en arrière-plan.  
4. **L'apparence peut être trompeuse** : Prometheus indiquait que la cible était `UP` avec un scrape récent, ce qui suggérait que tout fonctionnait. C'était techniquement vrai : Prometheus arrivait bien à joindre **une** instance, mais ce n'était pas la bonne.

## 6\. Recommandations pour éviter la récidive

### À court terme

- **Toujours fermer uvicorn proprement** avec `Ctrl+C` plutôt que de fermer la fenêtre PowerShell directement.  
- **Vérifier régulièrement** avec `netstat -ano | findstr :8001` qu'aucun processus orphelin ne traîne, surtout après un redémarrage du PC.

### À moyen terme

- **Utiliser uniquement le container Docker pour l'API** : ne plus lancer uvicorn en local en parallèle. Si besoin de développer avec du hot-reload, configurer le hot-reload dans le `Dockerfile.api` lui-même.  
- **Ajouter un check au démarrage du script de prédictions** : avant de lancer le trafic, vérifier qu'il n'y a qu'un seul processus écoutant sur le port 8001, et alerter sinon.

### À long terme

- **Configurer Alertmanager** pour détecter automatiquement les situations où Prometheus scrape avec succès mais ne reçoit pas de métriques applicatives (par exemple, alerte si `routezone_predictions_total` n'augmente pas pendant 1 heure malgré un statut UP).


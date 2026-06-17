# Carnet de bord — Veille technologique

## Introduction

Ce carnet documente ma veille technologique structurée sur les thématiques liées au projet RouteZone : Machine Learning, classification déséquilibrée, métriques d'évaluation, et bonnes pratiques de production.

Ma veille s'est formalisée en mai 2026, dans la phase de consolidation du projet et de préparation des rapports de certification. Auparavant, mes recherches étaient plus informelles (échanges avec mes formateurs, exploration ciblée lors du développement (vidéo YouTube, datacamp...), recours à Claude pour structurer les concepts).

Chaque article est documenté avec :
- Source et critères de fiabilité
- Synthèse rédigée avec mes propres mots
- Lien explicite avec mon projet RouteZone

---

## Article 1 - Mardi 12 mai 2026

- **Titre** : Comment gérer le déséquilibre des classes (imbalanced dataset) en machine learning ?
- **Source** : La revue IA
- **Date publication** : 8 mars 2021
- **Auteur** : Ilyes Talbi
- **Lien** : https://larevueia.fr/comment-gerer-le-desequilibre-des-classes-en-machine-learning/
- **Critères de fiabilité** : La revue IA est un site français de vulgarisation Machine Learning créé par Ilyes Talbi, ingénieur Data. Articles structurés, références techniques (scikit-learn, papers académiques), bonne pédagogie. Source recommandée par plusieurs formateurs Data Science. Le contenu sur le déséquilibre des classes est cohérent avec la documentation officielle de scikit-learn et les bonnes pratiques du milieu.

- **Ce que j'en retiens** :

Le déséquilibre des classes doit être géré en machine learning. Par exemple, en e-commerce, si l'on souhaite mettre en place un modèle qui prédit les fraudes, il faut tenir compte du déséquilibre des classes : la majorité des transactions n'étant pas frauduleuses, elles ont un poids plus conséquent dans le modèle, qui devient alors incapable de détecter les fraudes.

Pour pallier ce problème, plusieurs méthodes existent :

- **Méthodes "data-level"** : transformations opérées sur les données d'entraînement pour atténuer le déséquilibre.
  - **Sous-échantillonnage aléatoire** de la classe majoritaire
  - **Tomek Links** : approche de sous-échantillonnage qui supprime les points de la classe majoritaire proches d'un point de la classe minoritaire
  - **SMOTE** : technique de sur-échantillonnage de la classe minoritaire par génération de points synthétiques

- **Méthodes "algorithm-level"** : modifications des modèles utilisés pour qu'ils soient plus adaptés au déséquilibre.
  - **Apprentissage sensible aux coûts** : attribuer un poids plus important à la classe minoritaire pour faire comprendre au modèle que bien classer un point minoritaire est plus important. Implémentation via le paramètre `sample_weights` (disponible dans Random Forest de scikit-learn).
  - **Apprentissage à une classe** : on entraîne le modèle uniquement sur la classe majoritaire ; il sera ensuite capable de prédire si un point fait partie ou non de cette classe.

- **À noter** :
  - Le choix des **métriques** est fondamental : pour pallier le déséquilibre, la matrice de confusion, le recall (sensibilité) et le F1-score sont à privilégier (l'accuracy est trompeuse).
  - La **qualité du dataset** est un fondamental. Identifier un déséquilibre de classes en amont est crucial pour la suite du projet : une bonne compréhension de son dataset conditionne tous les choix méthodologiques.

- **Lien avec mon projet RouteZone** : Mon dataset BAAC présente un fort déséquilibre (environ 17% de cas "Grave" contre 83% de cas "Pas grave"). J'ai appliqué l'approche **algorithm-level** via la pondération des classes (`class_weight='balanced'` dans LightGBM), et privilégié les métriques **Recall (GRAVE)** et **F1-macro** plutôt que l'accuracy. SMOTE a été testé puis abandonné car il dégradait la généralisation du modèle.

---

## Article 2 - Mardi 12 mai 2026

- **Titre** : XGBoost vs Random Forest : prédire la gravité d'un accident de la route
- **Source** : La revue IA
- **Date publication** : 6 septembre 2020
- **Auteur** : Ilyes Talbi
- **Lien** : https://larevueia.fr/xgboost-vs-random-forest-predire-la-gravite-dun-accident-de-la-route/
- **Critères de fiabilité** : Article du même auteur que l'article 1, sur la même plateforme (La revue IA). Source confirmée comme fiable. Article publié en 2020, donc à recouper avec des sources plus récentes (j'ai utilisé la documentation LightGBM et scikit-learn récente pour mon implémentation, qui n'existaient pas dans l'article original).

- **Ce que j'en retiens** :

Cet article est un **tutoriel d'introduction** qui traite la même problématique que mon projet RouteZone : prédire la gravité d'un accident à partir des données BAAC publiées sur data.gouv.fr. L'auteur utilise les 4 mêmes fichiers que moi (caractéristiques, lieux, véhicules, victimes/usagers) et compare deux algorithmes : Random Forest et GradientBoostingClassifier (présenté comme XGBoost).

**Démarche de l'auteur** :
- Fusion des 4 fichiers via la clé `Num_Acc`
- Gestion des valeurs manquantes (suppression des variables avec trop de NaN plutôt que suppression de lignes)
- Encodage One-Hot via `pd.get_dummies()`
- Entraînement de Random Forest (n_estimators=100, max_depth=8) et GradientBoosting (learning_rate=0.2, max_depth=5)
- Évaluation avec accuracy, recall (macro) et F1-score (macro)

**Conclusion de l'auteur** : XGBoost est légèrement meilleur que Random Forest, mais les résultats restent "décevants". L'auteur reconnaît lui-même que le **déséquilibre des classes** est une limite majeure non traitée dans ce tutoriel.

- **Limites de l'article** :
  - Tutoriel d'**introduction** non destiné à la production (l'auteur le précise : "Nous ne chercherons pas à optimiser les scores obtenus")
  - Pas d'optimisation des hyperparamètres (GridSearch mentionné mais pas appliqué)
  - Pas de gestion du déséquilibre des classes (problème évoqué en conclusion uniquement)
  - Pas d'industrialisation (pas d'API, pas d'application, pas de monitoring)
  - Une seule année de données

- **Lien avec mon projet RouteZone** : Cet article confirme la pertinence de ma démarche tout en montrant la valeur ajoutée de mon approche par rapport à un tutoriel d'introduction :

| Critère | Article Ilyes Talbi | Mon projet RouteZone |
|---|---|---|
| Volume données | 1 année | **3 années** (153 054 accidents) |
| Modèles testés | 2 (RF + GradientBoosting) | **4** (LogReg + RF + XGBoost + LightGBM) |
| Optimisation | Aucune | **Optuna** |
| Déséquilibre classes | Non traité | **Géré** (pondération + métriques adaptées) |
| Métriques | Accuracy, Recall, F1 | **Recall GRAVE + F1 macro + AUC-ROC** |
| Enrichissement données | Aucun | **Open-Meteo (météo réelle) + OSRM (temps intervention pompiers/SAU)** |
| Industrialisation | Aucune | **API FastAPI + Streamlit + PostgreSQL + Docker + Prometheus/Grafana + 34 tests pytest + CI/CD** |

Cet article m'a confirmé que les approches Random Forest et boosting sont pertinentes pour ce type de problème, ce qui justifie mon choix de **LightGBM** (algorithme de gradient boosting plus moderne et performant que XGBoost sur ce type de données tabulaires déséquilibrées).

---

## Article 3 - Vendredi 15 mai 2026

- **Titre** : Précision et Rappel : Arrête de te tromper !
- **Source** : Mon Shot de Data Science (newsletter Substack)
- **Date publication** : non clairement identifiée sur la page consultée
- **Auteur** : non clairement identifié sur la page consultée
- **Lien** : https://www.monshotdata.com/p/preecision-vs-rappel
- **Critères de fiabilité** : Newsletter Substack spécialisée en Data Science en français. **Limites identifiées** : auteur et date de publication non clairement affichés sur la page. J'ai donc recoupé les notions abordées (précision, rappel, F1-score) avec d'autres sources documentées (articles d'Ilyes Talbi sur La revue IA, documentation scikit-learn officielle). Le contenu est cohérent avec ces sources de référence et avec mes connaissances techniques. Cette démarche de recoupement illustre l'importance de la triangulation des sources en veille technologique.

- **Ce que j'en retiens** :

La **précision** répond à la question suivante : **parmi toutes les prédictions dites positives, combien sont réellement positives ?** Le but n'est pas de trouver TOUS les positifs mais plutôt que tous les positifs prédits SOIENT CORRECTS. Par exemple : si dans notre échantillon nous avons 6 bons livres et 6 mauvais livres et que le modèle en prédit 2, ce qui importe c'est de savoir si les 2 prédits font partie de ces 6 bons livres et pas des 6 mauvais livres. Certes, 4 livres seront passés à la trappe mais tant que le modèle prédit correctement, c'est ce qui compte ! **Autrement dit : ce que le modèle a classifié comme « Positif » était bien « Positif ».**

En revanche, le **Rappel** est un peu différent. Il répond à la question suivante : **quelle proportion des échantillons réellement positifs a été correctement identifiée par le modèle ?** Ici, le but est que le modèle DÉTECTE TOUS LES CAS POSITIFS. Si on reprend l'exemple des livres ci-dessus, admettons que le modèle prédit 7 livres bons (répartis en 6 livres bons + 1 livre mauvais). Tous les échantillons positifs ont été classifiés correctement. Donc le rappel est bon, même si certaines prédictions positives n'étaient pas réellement positives (ici un livre mauvais). **Mais tous les échantillons positifs doivent être classifiés comme positifs.**

- **Lien avec mon projet RouteZone** : Cet article justifie directement mon choix de privilégier la métrique **Recall** dans RouteZone. Pour des raisons métier de sécurité routière, il m'est indispensable de détecter TOUS les accidents GRAVE, même au prix de fausses alertes : il vaut mieux une fausse alerte qu'un accident grave non détecté. Le coût d'un faux négatif (rater un accident grave) est bien supérieur au coût d'un faux positif (envoyer les secours pour rien).

La Precision n'est pas la métrique prioritaire ici, car son objectif est différent : elle vise la qualité des prédictions positives (être correct quand on dit "grave"), pas l'exhaustivité de la détection.

C'est pourquoi mon modèle V3 OSRM final affiche un **Recall GRAVE de 76,43%** (objectif métier prioritaire) au détriment d'une Precision plus modeste de 41,66% (acceptable dans ce contexte de sécurité).

---

## Notes de compréhension

### Note 1 - Mardi 12 mai 2026 — Accuracy et déséquilibre des classes

L'accuracy est une métrique trompeuse en présence de classes déséquilibrées car elle se base sur la performance globale du modèle, dominée par la classe majoritaire.

**Exemple** : sur mon dataset RouteZone avec 83% de "Pas grave" et 17% de "Grave", un modèle qui prédirait systématiquement "Pas grave" obtiendrait 83% d'accuracy, alors qu'il raterait 100% des accidents graves. C'est précisément ce qu'on veut éviter en sécurité routière.

C'est pourquoi mon projet utilise les métriques suivantes (test 2024, 148 506 accidents) :

- **Recall sur la classe GRAVE : 76,43 %** → capacité à détecter les vrais graves
- **Precision sur la classe GRAVE : 41,66 %** → quand on dit "Grave", on a raison 42% du temps
- **F1 macro : 69,56 %** → équilibre précision/rappel sur les 2 classes
- **AUC-ROC : 85,58 %** → qualité globale de séparation des classes
- **Accuracy : 78 %** → présentée pour comparaison mais non décisionnelle

**Arbitrage métier assumé** : on privilégie le Recall (détecter le maximum de cas graves) au détriment de la Precision (faux positifs acceptables), car le coût d'un accident grave non détecté est bien supérieur au coût d'une fausse alerte.

Modèle utilisé : LightGBM V3 OSRM, fichier `best_model_v3_osrm.pkl`, entraîné sur BAAC 2022-2023, testé sur BAAC 2024 entier.


## Article 4 - Vendredi 15 mai 2026
 
- **Titre** : How To Use Optuna to Tune LightGBM Hyperparameters
- **Source** : Forecastegy (blog spécialisé Data Science / forecasting)
- **Date publication** : 7 avril 2023
- **Auteur** : Mario Filho (Kaggle Grandmaster)
- **Lien** : https://forecastegy.com/posts/how-to-use-optuna-to-tune-lightgbm-hyperparameters/
- **Critères de fiabilité** : Auteur identifié et qualifié (Kaggle Grandmaster), date et temps de lecture affichés clairement. Le contenu est cohérent avec la documentation officielle Optuna et LightGBM. **Limite identifiée** : article de 2023, donc certaines API ont pu évoluer ; j'ai recoupé la syntaxe `trial.suggest_*` et `create_study` avec la documentation Optuna à jour, qui reste valide.
- **Ce que j'en retiens** :
L'auteur recommande de **tuner les hyperparamètres AVANT le feature engineering**, avec une métaphore de cuisine : ajuster les bons ingrédients avant d'expérimenter de nouvelles saveurs. Il insiste sur un point important : ne pas re-tuner après le feature engineering, car les gains sont marginaux et le risque d'overfitting augmente.
 
Il identifie **6 hyperparamètres réellement utiles** pour LightGBM : le nombre d'arbres (`num_iterations`), le `learning_rate` (entre 0.001 et 0.1, à l'échelle logarithmique), le `num_leaves` (complexité de l'arbre, à tester en puissances de 2), le `subsample`, le `colsample_bytree`, et le `min_data_in_leaf`.
 
L'optimisation repose sur l'**optimisation bayésienne** d'Optuna, présentée comme un chercheur de trésor avec un détecteur de métaux intelligent, par opposition au random search (creuser des trous au hasard) ou au grid search (ratisser toute la zone). Environ 30 trials suffisent généralement pour obtenir un bon jeu d'hyperparamètres.
 
- **Lien avec mon projet RouteZone** : Cet article valide directement ma démarche d'optimisation par **Optuna** dans le notebook 08, où j'ai tuné LightGBM pour maximiser le Recall GRAVE. La logique "tuner avant le feature engineering" éclaire aussi ma chronologie de travail : ma vraie rupture de performance n'est pas venue du tuning mais de l'enrichissement des features (passage Haversine puis OSRM Golden Hour), ce qui rejoint l'idée de l'auteur que le feature engineering a souvent plus d'impact que le tuning lui-même. Le conseil sur le `learning_rate` en échelle log et le `num_leaves` en puissances de 2 correspond à ce que j'ai paramétré dans mon espace de recherche Optuna.
---
 
## Article 5 - Mardi 19 mai 2026
 
- **Titre** : How to Use LightGBM with Optuna for Hyperparameter Tuning
- **Source** : Woteq Zone (blog technique)
- **Date publication** : février 2026
- **Auteur** : non clairement identifié sur la page consultée
- **Lien** : https://woteq.com/how-to-use-lightgbm-with-optuna-for-hyperparameter-tuning
- **Critères de fiabilité** : Article très récent (février 2026), ce qui est appréciable en veille. **Limite identifiée** : auteur non affiché clairement. J'ai recoupé les notions clés (define-by-run, `suggest_float`/`suggest_int`, pruning, visualisation) avec la documentation Optuna officielle et avec l'article de Mario Filho ci-dessus ; le contenu est cohérent. Cette redondance entre deux sources indépendantes renforce ma confiance.
- **Ce que j'en retiens** :
L'article présente LightGBM comme un framework de gradient boosting développé par Microsoft, rapide et scalable, populaire sur les compétitions de données tabulaires type Kaggle. Optuna y est décrit comme un framework d'optimisation automatique des hyperparamètres.
 
Deux bonnes pratiques sont mises en avant. D'abord, **visualiser l'étude** avec les fonctions `optuna.visualization` pour tracer l'importance des paramètres et l'historique d'optimisation, ce qui donne une vraie lecture du processus de tuning. Ensuite, la **loi des rendements décroissants** : les gains les plus importants viennent des premiers trials, il est inutile de lancer des milliers d'essais pour un gain infime.
 
- **Lien avec mon projet RouteZone** : Confirme la pertinence de mon couple LightGBM + Optuna sur des données tabulaires (BAAC 2022-2024). Le conseil de visualiser l'importance des hyperparamètres complète mon analyse, où j'ai surtout regardé l'importance des features (la feature OSRM Golden Hour ressortant en tête). Je peux mentionner à l'oral que je me suis arrêtée à un nombre raisonnable de trials, en accord avec la loi des rendements décroissants, plutôt que de sur-optimiser inutilement.
---
 
## Article 6 - Samedi 23 Mai 2026
 
- **Titre** : How to Calculate Precision, Recall, and F-Measure for Imbalanced Classification
- **Source** : MachineLearningMastery.com
- **Date publication** : 2 août 2020 (mise à jour)
- **Auteur** : Jason Brownlee (PhD, spécialiste ML reconnu)
- **Lien** : https://machinelearningmastery.com/precision-recall-and-f-measure-for-imbalanced-classification/
- **Critères de fiabilité** : Auteur identifié et reconnu dans le domaine, source de référence très citée. Contenu appuyé sur des ouvrages académiques (*Imbalanced Learning: Foundations, Algorithms, and Applications*, 2013) et sur la documentation scikit-learn. Fiabilité élevée. **Limite** : article ancien (2020), mais les définitions de précision/rappel/F-mesure sont stables et indémodables.
- **Ce que j'en retiens** :
L'**accuracy est inappropriée** en classification déséquilibrée : un modèle peut atteindre 90 ou 99% d'accuracy en ignorant simplement la classe minoritaire. D'où l'usage de la précision et du rappel.
 
La **précision** mesure, parmi les prédictions positives, combien sont réellement positives : `TP / (TP + FP)`. Maximiser la précision revient à minimiser les faux positifs.
 
Le **rappel** mesure la couverture de la classe minoritaire : parmi tous les vrais positifs, combien ont été détectés : `TP / (TP + FN)`. Maximiser le rappel revient à minimiser les faux négatifs.
 
La **F-mesure (F1)** est la moyenne harmonique des deux, et donne un score unique quand on veut équilibrer les deux préoccupations. L'auteur rappelle un point clé : augmenter le rappel se fait souvent au détriment de la précision, car détecter plus de positifs augmente aussi les faux positifs.
 
- **Lien avec mon projet RouteZone** : Cet article est le socle théorique de mon choix de métrique. En sécurité routière, le **faux négatif (rater un accident GRAVE)** a un coût bien supérieur au faux positif (mobiliser les secours pour rien). J'ai donc priorisé le **Recall GRAVE (0,7643)** quitte à accepter une Precision plus modeste (0,4166), ce qui correspond exactement à la logique "Recall approprié quand minimiser les faux négatifs est l'objectif". Mon F1 macro (0,6956) et mon AUC-ROC (0,8558) complètent la lecture. Cet article justifie aussi pourquoi je n'ai PAS retenu l'accuracy comme métrique de pilotage.
---
 
## Article 4 - Lundi 25 mai 2026
 
- **Titre** : Class Imbalance in Machine Learning
- **Source** : Train in Data's Blog (blog de formation ML, équipe autour de Soledad Galli)
- **Date publication** : 17 septembre 2025
- **Auteur** : non nominativement identifié sur la page consultée (éditeur : Train in Data)
- **Lien** : https://www.blog.trainindata.com/class-imbalance-in-machine-learning/
- **Critères de fiabilité** : Blog spécialisé en données déséquilibrées, reconnu pour ses cours sur le sujet. Date récente. **Limite identifiée** : auteur individuel non affiché sur la page. J'ai recoupé la notion de `class_weight='balanced'` et de cost-sensitive learning avec la documentation scikit-learn officielle et avec l'article de Jason Brownlee ; le contenu est cohérent.
- **Ce que j'en retiens** :
L'article détaille le **cost-sensitive learning** comme approche directe du déséquilibre : on pénalise plus fortement le modèle quand il se trompe sur la classe minoritaire, en lui assignant un poids supérieur.
 
Dans scikit-learn, cela passe par le paramètre `class_weight` disponible sur la régression logistique, les arbres, les random forests et le gradient boosting. Quand `class_weight='balanced'`, **chaque classe reçoit un poids inversement proportionnel à sa fréquence** (le ratio de déséquilibre).
 
L'article recommande d'évaluer les modèles déséquilibrés avec la matrice de confusion, la précision, le rappel, le F1-score, la courbe ROC ou la balanced accuracy, plutôt qu'avec l'accuracy seule.
 
- **Lien avec mon projet RouteZone** : Justifie directement mon choix de `class_weight='balanced'` en V2, retenu plutôt que SMOTE-NC. C'est l'argument technique que je présente au jury : plutôt que de générer des exemples synthétiques (SMOTE), j'ai pénalisé les erreurs sur la classe GRAVE minoritaire via la pondération inverse de fréquence, approche plus simple et qui préserve la distribution réelle des données. Cela explique aussi pourquoi mon tableau de métriques met en avant rappel, précision, F1 macro et AUC, et non l'accuracy.
---
 
## Article 5 - Mercredi 27 mai 2026
 
- **Titre** : Handling Imbalanced Data for Classification
- **Source** : GeeksforGeeks
- **Date publication** : 2 février 2026
- **Auteur** : rédaction collective GeeksforGeeks (pas d'auteur individuel)
- **Lien** : https://www.geeksforgeeks.org/machine-learning/handling-imbalanced-data-for-classification/
- **Critères de fiabilité** : Plateforme pédagogique très consultée, contenu récent et accessible. **Limite identifiée** : pas d'auteur nommé, qualité parfois inégale sur GeeksforGeeks. J'ai recoupé les techniques décrites (resampling, threshold moving, F1) avec les deux articles précédents et la documentation scikit-learn, qui les confirment.
- **Ce que j'en retiens** :
L'article fait le tour des techniques de gestion du déséquilibre. Le **resampling** ajuste la taille des classes : l'oversampling duplique ou génère des exemples de la classe minoritaire, l'undersampling réduit la classe majoritaire.
 
Il insiste sur le **déplacement du seuil de décision** : en entraînant un classifieur puis en prédisant des probabilités plutôt que des labels directs, on peut faire varier le seuil pour observer l'évolution du F1-score et trouver un meilleur équilibre.
 
Point pédagogique utile : la précision et le F1 chutent avec les faux positifs, tandis que le rappel et le F1 chutent quand on manque des exemples de la classe minoritaire. Le F1 ne s'améliore que si précision ET rappel progressent ensemble, ce qui en fait une bonne métrique pour les données déséquilibrées.
 
- **Lien avec mon projet RouteZone** : Me donne une vue d'ensemble des alternatives que j'ai pu écarter ou retenir. J'ai privilégié la pondération de classe au resampling, mais je peux expliquer au jury que je connais les autres leviers (oversampling, undersampling, threshold moving). La notion de seuil de décision est particulièrement pertinente : elle me permet d'expliquer que j'aurais pu ajuster le seuil de probabilité pour pousser encore le rappel, et de relier cela à mon abandon de la calibration (CalibratedClassifierCV faisait chuter mon Recall GRAVE de 76% à 33%).
---
 
## Article 6 - Vendredi 29 mai 2026
 
- **Titre** : Grafana Tutorial: A Beginner's Guide to Monitoring Machine Learning Models
- **Source** : DataCamp
- **Date publication** : août 2024 (à vérifier précisément sur la page)
- **Auteur** : non confirmé sur la page consultée
- **Lien** : https://www.datacamp.com/tutorial/grafana-tutorial-monitoring-machine-learning-models
- **Critères de fiabilité** : DataCamp est une plateforme de formation Data reconnue. **Limite identifiée** : auteur et date exacte non confirmés lors de ma consultation. J'ai recoupé l'architecture décrite (FastAPI + Prometheus + Grafana + Docker) avec mon propre stack RouteZone fonctionnel et avec les autres articles de monitoring de cette veille, qui décrivent le même schéma.
- **Ce que j'en retiens** :
L'article décrit un pipeline complet de monitoring ML. On expose le modèle via une API REST (Flask ou **FastAPI**), on instrumente les métriques avec le client Prometheus, et **Prometheus scrape** ces métriques exposées sur un endpoint dédié.
 
Une dimension intéressante : la **détection de dérive** (data drift et concept drift). À l'aide d'APScheduler, on planifie une fonction Python qui s'exécute à intervalles réguliers (par exemple chaque minute) pour récupérer les nouvelles données de production, lancer les algorithmes de détection de drift, et exposer les scores que Prometheus viendra récupérer.
 
L'ensemble est ensuite **dockerisé**, et **Grafana** visualise les métriques.
 
- **Lien avec mon projet RouteZone** : C'est le miroir quasi exact de mon architecture de monitoring : conteneurs `routezone_api` (FastAPI), `routezone_prometheus`, `routezone_grafana`, orchestrés via Docker Compose. L'article me donne une piste d'évolution à mentionner à l'oral : ajouter une **détection de dérive** planifiée pour surveiller si la distribution des nouveaux accidents s'éloigne de celle des données BAAC d'entraînement. C'est un axe d'amélioration crédible pour la partie MLOps de ma soutenance.
---
 
## Article 7 - Mardi 2 juin 2026
 
- **Titre** : Prometheus and Grafana for ML Monitoring: Complete Setup Guide
- **Source** : Reintech (blog technique / media)
- **Date publication** : 23 janvier 2026
- **Auteur** : non clairement identifié sur la page consultée
- **Lien** : https://reintech.io/blog/prometheus-grafana-ml-monitoring-setup-guide
- **Critères de fiabilité** : Article très récent, orienté pratique avec exemples de code et règles d'alerte. **Limite identifiée** : auteur non affiché. J'ai recoupé les commandes et le rôle de chaque outil avec la documentation officielle Prometheus et Grafana, et avec ma propre configuration RouteZone.
- **Ce que j'en retiens** :
L'article part d'une question concrète : une fois le modèle déployé, comment savoir s'il fonctionne réellement comme attendu ? Sans monitoring, on est aveugle ; le modèle peut faire de mauvaises prédictions, saturer la mémoire ou répondre trop lentement sans qu'on le sache.
 
La solution Prometheus + Grafana donne une **visibilité temps réel** sur la performance du modèle, l'usage des ressources et la qualité des prédictions. L'article conseille de commencer simple (taux de requêtes et latence) puis d'ajouter des métriques spécifiques au cas d'usage : distribution des features en entrée, taux de cache, dépendances vers d'autres services.
 
Point important sur les **alertes** : ne configurer que celles qui justifient une intervention immédiate, pour ne pas être noyé sous des notifications inutiles.
 
- **Lien avec mon projet RouteZone** : Conforte mon choix d'instrumenter l'API avec Prometheus et de visualiser dans Grafana. Le conseil "commencer par latence et taux de requêtes, puis enrichir" décrit bien ma progression. Le passage sur les alertes m'ouvre un axe d'évolution à citer : définir des règles d'alerte (par exemple si la latence de prédiction dépasse un seuil, ou si le taux de prédictions GRAVE dévie anormalement). À noter pour la démo : mon Grafana est accessible via http://[::1]:3000 à cause du souci IPv6/IPv4 Docker sous Windows.
---
 
## Article 8 - Lundi 8 Juin 2026
 
- **Titre** : FastAPI Observability Lab with Prometheus and Grafana: Complete Guide
- **Source** : Towards AI
- **Date publication** : 4 décembre 2025
- **Auteur** : non confirmé sur la page consultée
- **Lien** : https://towardsai.net/p/machine-learning/fastapi-observability-lab-with-prometheus-and-grafana-complete-guide
- **Critères de fiabilité** : Towards AI est une publication tech reconnue. Date récente. **Limite identifiée** : auteur non confirmé lors de ma consultation. J'ai recoupé la distinction métriques/logs/traces et l'usage de PromQL avec la documentation Grafana officielle.
- **Ce que j'en retiens** :
L'article est un lab pratique d'**observabilité** d'une application FastAPI avec des outils standards de l'industrie. Il distingue les trois piliers de l'observabilité : les **métriques** (mesures quantitatives dans le temps, l'objet du lab), les **logs** (événements horodatés) et les **traces** (parcours d'une requête dans un système distribué).
 
Côté apprentissage : comment instrumenter une application FastAPI avec des métriques Prometheus, comment Prometheus scrape et stocke ces métriques, et comment construire des dashboards Grafana à l'aide de **requêtes PromQL**.
 
- **Lien avec mon projet RouteZone** : M'apporte un vocabulaire structurant pour ma soutenance (la triade métriques / logs / traces), utile pour situer ce que je fais réellement : je suis sur les métriques. PromQL est le langage que j'utilise dans Grafana pour interroger Prometheus ; cet article me permet d'en parler avec les bons termes. Je peux aussi mentionner que logs et traces seraient les étapes suivantes d'une observabilité plus complète si RouteZone passait en production réelle.
---
 
## Article 9 - Vendredi 12 Juin 2026
 
- **Titre** : Demonstrating MLflow: A Beginner's Guide to Experiment Tracking
- **Source** : Medium
- **Date publication** : 31 décembre 2025
- **Auteur** : Debashish Mishra
- **Lien** : https://medium.com/@debashishmishra888/demonstrating-mlflow-a-beginners-guide-to-experiment-tracking-bb545fc74ce4
- **Critères de fiabilité** : Auteur identifié, date récente, contenu pratique (captures, commandes). **Limite identifiée** : article de blog personnel sur Medium, donc non revu par les pairs. J'ai recoupé les fonctionnalités décrites avec la documentation MLflow officielle, qui les confirme.
- **Ce que j'en retiens** :
L'auteur présente MLflow comme un **carnet de bord** pour les projets ML : au lieu de noter à la main ce qu'on a essayé en espérant s'en souvenir, MLflow enregistre tout automatiquement.
 
Trois usages clés : **tracer les expériences** (chaque entraînement est enregistré, on ne perd plus la trace de la version qui marchait le mieux), **logguer paramètres, métriques et modèles** (les entrées comme le learning rate, les résultats comme l'accuracy, et le modèle lui-même), et **comparer facilement les runs** côte à côte.
 
L'interface se lance avec `mlflow ui`, accessible par défaut sur http://127.0.0.1:5000, où l'on peut visualiser les runs, comparer les métriques, inspecter les paramètres et télécharger les modèles.
 
- **Lien avec mon projet RouteZone** : Décrit exactement l'usage que j'ai fait de MLflow dans le notebook 08. Mon expérience s'appelle "zone_route v3Courses" avec le run "modele_v3_osrm". J'ai loggé mes hyperparamètres Optuna, mes métriques (Recall GRAVE, Precision, F1 macro, AUC-ROC) et mes modèles, ce qui m'a permis de **comparer mes runs** et de tracer l'historique des versions (V1 baseline, V2 Haversine, V3 OSRM). C'est précisément ce qui m'a permis de documenter l'incident du calibrateur (chute du Recall GRAVE) avant de l'écarter.
---
 
## Article 10 - Mardi 16 juin 2026
 
- **Titre** : MLflow Mastery: A Complete Guide to Experiment Tracking and Model Management
- **Source** : KDnuggets
- **Date publication** : non clairement datée sur la page consultée
- **Auteur** : non clairement identifié sur la page consultée
- **Lien** : https://www.kdnuggets.com/mlflow-mastery-a-complete-guide-to-experiment-tracking-and-model-management
- **Critères de fiabilité** : KDnuggets est une référence historique en Data Science / ML. **Limite identifiée** : ni auteur ni date clairement affichés lors de ma consultation. J'ai recoupé l'ensemble des fonctionnalités (Tracking, Projects, Models, Registry) avec la documentation MLflow officielle et avec l'article de Debashish Mishra ci-dessus ; les deux sources concordent, ce qui sécurise le contenu.
- **Ce que j'en retiens** :
L'article positionne MLflow comme la réponse au désordre des projets ML (expériences éparpillées, déploiements inefficaces). Quatre composantes structurent la plateforme : le **Tracking** (log des paramètres, métriques et artefacts), la **reproductibilité** (sauvegarde des réglages exacts de chaque test), le **versioning de modèles** via le **Model Registry**, et la **scalabilité** (intégration avec TensorFlow, PyTorch, scikit-learn, stockage cloud).
 
Le Tracking logge quatre types d'éléments : les paramètres (hyperparamètres), les métriques (accuracy, précision, rappel, loss), les artefacts (modèles, datasets, graphiques) et la version exacte du code. Bonnes pratiques recommandées : centraliser le tracking pour le travail d'équipe, versionner code/données/modèles, et standardiser les workflows.
 
- **Lien avec mon projet RouteZone** : Complète l'article 9 en allant plus loin que le simple tracking : il introduit le **Model Registry** et la reproductibilité, deux notions que je peux citer comme axes de maturité MLOps. Aujourd'hui, j'utilise surtout le Tracking et le logging d'artefacts (mon modèle final `best_model_v3_osrm.pkl`). Mentionner le Model Registry me permet de montrer au jury que je connais la suite logique : promouvoir un modèle en "production" de façon versionnée, plutôt que de pointer un fichier .pkl. C'est un bon argument pour la projection "et après" de ma soutenance.



---

## Mon dispositif de veille

| Type | Outils / Sources |
|---|---|
| **Agrégateurs** | Daily.dev (tags : ML, Python, Data Science) |
| **Newsletters** | The Batch (Andrew Ng), DataScientest hebdo, Mon Shot de Data Science |
| **YouTube** | Machine Learnia (Guillaume Saint-Cirgue), Defend Intelligence |
| **Sites de référence** | La revue IA (Ilyes Talbi), DataCamp, scikit-learn docs |
| **Recherche ciblée** | Google Scholar, ArXiv pour les besoins précis |
| **Accompagnement IA** | Claude (Anthropic) pour structurer, comprendre et reformuler les concepts |




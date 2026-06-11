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
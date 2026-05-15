# Incident #001 — Désactivation du calibrator V3 OSRM

## Métadonnées

| Champ | Valeur |
|---|---|
| **Date de détection** | 13 mai 2026 |
| **Date de résolution** | 14 mai 2026 |
| **Sévérité** | Critique (impact métier majeur) |
| **Composant impacté** | `src/api/routes_ia.py` — endpoint `/predict` |
| **Modèle concerné** | V3 OSRM (`best_model_v3_osrm.pkl` + `calibrator_v3_osrm.pkl`) |
| **Type d'incident** | Bug fonctionnel silencieux (aucune erreur technique, mais sortie modèle dégradée) |
| **Détectrice** | Meriem Abdelouahed |
| **Méthode de détection** | Vérification empirique des métriques en production |

---

## 1. Contexte

### 1.1 Présentation du système

RouteZone est un service de prédiction de la gravité des accidents routiers (binaire : Grave / Pas grave) basé sur les données BAAC 2022-2024. Le modèle utilisé est un **LightGBM V3 OSRM** entraîné sur 265 064 accidents (2022-2023) et évalué sur 148 506 accidents (2024 entier — split temporel).

### 1.2 Définitions techniques

Pour comprendre cet incident, plusieurs concepts doivent être explicités :

**LightGBM** : bibliothèque open-source de Machine Learning développée par Microsoft, qui implémente l'algorithme du **gradient boosting**. Le gradient boosting consiste à entraîner séquentiellement plusieurs arbres de décision, chaque nouvel arbre corrigeant les erreurs du précédent. Le résultat final est une combinaison pondérée des prédictions de tous les arbres. LightGBM est reconnu pour sa vitesse et ses performances sur les données tabulaires.

**Score vs Probabilité empirique** : un score de prédiction est un nombre entre 0 et 1 qui reflète la confiance du modèle. Cependant, ce score n'est pas automatiquement une probabilité empirique. **Empirique** signifie "vérifié dans la réalité observée". Concrètement, si un modèle produit un score de 0.7, cela ne signifie pas littéralement "dans 70% des cas similaires, l'événement s'est produit dans la réalité". C'est uniquement un ordre relatif de confiance entre les prédictions.

**Calibration de modèle** : technique qui transforme les scores bruts d'un modèle pour qu'ils correspondent à de véritables probabilités empiriques observées sur les données. Après calibration, un score de 0.7 doit signifier "dans 70% des cas similaires observés, l'événement Grave s'est effectivement produit".

**CalibratedClassifierCV** : classe de scikit-learn permettant de calibrer un modèle existant. Elle propose deux méthodes principales :
- **Méthode "sigmoid"** : ajuste les scores via une fonction sigmoïde (une courbe en forme de S). Adaptée quand la distribution des scores est régulière.
- **Méthode "isotonic"** : ajustement non-paramétrique apprenant une fonction monotone croissante quelconque. Plus flexible mais nécessite davantage de données pour être stable.

**Pourquoi envisager de calibrer un modèle de gradient boosting ?** Les modèles de gradient boosting (XGBoost, LightGBM) optimisent la **discrimination** des classes (les séparer le mieux possible), pas la calibration des probabilités. Pour un système d'aide à la décision où la valeur affichée doit être interprétable par l'utilisateur (ex : "67% de risque d'accident grave"), la calibration est parfois recommandée pour rendre les probabilités empiriquement fiables.

**Note importante** : la calibration n'est **pas obligatoire** en production. La majorité des systèmes ML déployés utilisent des modèles non-calibrés car ce qui importe est généralement la décision finale (classification) et l'ordre relatif des prédictions, pas la valeur exacte de la probabilité.

### 1.3 Architecture du pipeline de prédiction (avant incident)

Le notebook `notebook_07_modelisation_v3_osrm.ipynb` produit 3 fichiers stockés dans `models/` :

| Fichier | Type | Rôle |
|---|---|---|
| `best_model_v3_osrm.pkl` | LGBMClassifier | Modèle LightGBM brut |
| `calibrator_v3_osrm.pkl` | CalibratedClassifierCV (isotonic) | Modèle LightGBM enveloppé d'une couche de calibration |
| `features_v3_osrm.pkl` | list[str] | Liste ordonnée des 34 features attendues |

L'API FastAPI (`src/api/routes_ia.py`) chargeait les 3 fichiers et utilisait le calibrator en priorité :

```python
# Code AVANT incident (ligne 216)
proba = (calibrator or model).predict_proba(X)[0]
```

Cette logique signifiait : "Si le calibrator existe sur disque, utilise-le pour la prédiction. Sinon, fallback sur le modèle brut."

### 1.4 État avant incident

- Modèle entraîné et calibrator sauvegardés le 5 mai 2026
- API en production avec calibrator actif servi par défaut
- Tests pytest verts : 34/34
- Aucun message d'erreur, aucune alerte système
- **Point critique** : le calibrator n'avait **jamais été évalué empiriquement** sur le test 2024. Le notebook 07 se contentait de créer et sauvegarder le calibrator, sans appeler `calibrator.predict_proba(X_test)` pour mesurer ses performances réelles.

---

## 2. Détection

### 2.1 Élément déclencheur

Le 13 mai 2026, lors d'une session de vérification des métriques du modèle en préparation de la rédaction du rapport E3, j'ai constaté une incohérence entre :

- Les métriques annoncées dans le notebook 07 (Recall 0.7643 sur test 2024)
- Le comportement réel observé via des prédictions sur Streamlit

J'ai notamment remarqué que des scénarios "moyens" donnaient des probabilités étonnamment **basses** sur la classe Grave (~25-30%), alors que des cas potentiellement graves passaient en "Pas grave".

### 2.2 Hypothèse initiale

L'écart suggérait que **le modèle servi par l'API n'était pas exactement celui évalué dans le notebook 07**. J'ai donc demandé une vérification du code de chargement dans `routes_ia.py`.

### 2.3 Découverte

Vérification du code (`src/api/routes_ia.py:216`) :

```python
proba = (calibrator or model).predict_proba(X)[0]
```

→ Le calibrator était utilisé en priorité, mais ses performances réelles n'avaient jamais été mesurées sur le test 2024.

**Conclusion à ce stade** : les chiffres dans le notebook (Recall 0.7643) correspondaient au **modèle brut**, pas au calibrator qui était réellement servi en production. Il fallait évaluer empiriquement le calibrator pour connaître ses vraies performances.

---

## 3. Diagnostic

### 3.1 Plan d'investigation

Pour mesurer les performances réelles du calibrator, j'ai ajouté une cellule au notebook 07 chargeant explicitement le fichier `calibrator_v3_osrm.pkl` depuis le disque et calculant ses métriques sur le test 2024 (même jeu de données que l'évaluation du modèle brut, garantissant une comparaison équitable).

### 3.2 Code d'évaluation

```python
# Cellule ajoutée au notebook 07 (id 9e3aad2e)
calibrator_loaded = joblib.load(MODELS_DIR / "calibrator_v3_osrm.pkl")
proba_cal = calibrator_loaded.predict_proba(X_test)[:, 1]
pred_cal = (proba_cal >= 0.5).astype(int)

metrics_cal = {
    "recall_grave": recall_score(y_test, pred_cal),
    "precision_grave": precision_score(y_test, pred_cal),
    "f1_macro": f1_score(y_test, pred_cal, average="macro"),
    "auc_roc": roc_auc_score(y_test, proba_cal),
    "accuracy": accuracy_score(y_test, pred_cal),
}

print(classification_report(y_test, pred_cal, target_names=["Pas grave", "Grave"]))
```

### 3.3 Résultats — Comparaison empirique

Exécution sur le test 2024 (148 506 accidents, prévalence GRAVE = 17.15%) :

| Métrique | Modèle brut (LightGBM) | Calibrator (isotonic) | Delta |
|---|---:|---:|---:|
| **Recall GRAVE** | 0.7643 | **0.3299** | **-0.4344** |
| Precision GRAVE | 0.4166 | 0.6504 | +0.2338 |
| F1 macro | 0.6956 | 0.6772 | -0.0185 |
| AUC-ROC | 0.8558 | 0.8458 | -0.0099 |
| Accuracy | 0.7760 | 0.8547 | +0.0787 |

### 3.4 Interprétation métier

**Le calibrator dégradait sévèrement le Recall sur la classe GRAVE : de 76.43% à seulement 32.99%.**

Concrètement, cela signifiait :
- Avec le modèle brut : **76% des accidents réellement graves** étaient correctement détectés
- Avec le calibrator : **seulement 33% des accidents réellement graves** étaient détectés, et **67% passaient en "Pas grave"**

Pour un système d'aide à la décision en sécurité routière, c'est l'inverse de l'objectif métier. Le coût d'un faux négatif (rater un accident grave et ne pas envoyer les secours) est bien supérieur au coût d'un faux positif (envoyer les secours pour rien).

L'amélioration apparente de l'Accuracy (+7.87 points) était trompeuse : elle reflétait simplement le fait que le calibrator prédisait plus souvent la classe majoritaire (Pas grave), ce qui gonfle artificiellement l'accuracy sur un dataset déséquilibré (paradoxe classique du déséquilibre des classes).

---

## 4. Cause racine

### 4.1 Pourquoi le calibrator a-t-il dégradé le Recall ?

La calibration isotonique re-mappe les scores du modèle pour qu'ils correspondent à des probabilités empiriques. **Effet de bord critique** : cette re-cartographie déplace effectivement la frontière de décision (le seuil à 0.5).

Sur un dataset déséquilibré (17% GRAVE / 83% PAS GRAVE) avec un modèle entraîné avec `class_weight="balanced"`, le modèle brut produit des scores élevés pour la classe minoritaire afin de compenser le déséquilibre. La calibration isotonique, en re-mappant ces scores selon la distribution empirique, écrase cette compensation et fait passer de nombreuses prédictions au-dessus de 0.5 en-dessous.

### 4.2 Pourquoi le problème n'avait-il pas été détecté ?

Trois facteurs ont contribué à la persistance silencieuse du bug :

1. **Absence d'évaluation du calibrator dans le notebook** : la cellule de création du calibrator (id `d62cf669`) faisait `joblib.dump(calibrator_v3, ...)` puis passait directement à la conclusion. Aucune ligne `calibrator.predict_proba(X_test)` n'avait été écrite.

2. **Tests pytest non sensibles à ce type de régression** : les tests automatisés (34/34 verts) vérifient le fonctionnement de l'API (statut 200, format de réponse, cohérence Pydantic, tests métier basiques) mais ne mesurent pas les métriques de performance sur le test set complet. Un test passant par 200 cas pré-définis ne suffit pas à détecter une dégradation de 43 points de Recall.

3. **Aucune erreur visible** : le calibrator fonctionnait techniquement (pas d'exception, statut 200), il produisait juste des prédictions dégradées sans aucune alerte.

---

### 4.3 Note technique avancée — Interaction calibration / class_weight

Un point méthodologique mérite d'être souligné : le `CalibratedClassifierCV` 
avec `cv=3` re-entraîne le modèle de base 3 fois en cross-validation interne. 
Cette ré-entraînement n'a pas nécessairement bien propagé le paramètre 
`class_weight='balanced'` qui était présent dans le modèle d'origine. 

Une alternative aurait été d'utiliser `cv='prefit'` :

```python
calibrator_v3 = CalibratedClassifierCV(model_v3, cv='prefit', method="isotonic")
calibrator_v3.fit(X_val, y_val)
```

Avec `cv='prefit'`, le calibrator aurait conservé exactement le modèle 
pondéré sans le ré-entraîner, et n'aurait fait que calibrer ses sorties.

De plus, indépendamment du paramètre `cv`, la calibration isotonique 
re-mappe les scores selon la fréquence empirique observée. Sur un dataset 
déséquilibré géré par `class_weight='balanced'`, le modèle brut produit 
volontairement des scores 'compensés' pour la classe minoritaire ; la 
calibration empirique défait cette compensation, expliquant la chute 
brutale du Recall.

Une amélioration future pourrait consister à tester :
- Une calibration avec `cv='prefit'` pour préserver la pondération
- Une calibration "sigmoid" (Platt scaling) qui est moins agressive
- Un ajustement manuel du seuil de décision (threshold tuning) après 
  calibration pour rétablir le Recall

## 5. Solution appliquée

### 5.1 Décision

Désactiver le calibrator du flux de prédiction, tout en conservant le fichier sur disque pour traçabilité (permettant une éventuelle réactivation future si une autre méthode de calibration s'avérait plus adaptée).

### 5.2 Modifications dans `src/api/routes_ia.py`

**Ligne 216 — Bypass du calibrator** :

```python
# AVANT
proba = (calibrator or model).predict_proba(X)[0]

# APRÈS
# Calibrator desactive (cf. NOTE TECHNIQUE plus haut) : on sert model directement.
proba = model.predict_proba(X)[0]
```

**Lignes 35-45 — Note technique au chargement du modèle** :

```python
if v3_path.exists():
    model = joblib.load(v3_path)
    features = joblib.load(MODELS_DIR / "features_v3_osrm.pkl")
    # NOTE TECHNIQUE - Calibrator desactive depuis le 14 mai 2026
    # Le CalibratedClassifierCV isotonique degradait le Recall sur
    # la classe GRAVE (76% -> 33%) sur le test 2024 (voir notebook 07
    # cellule d'evaluation). Le fichier est conserve pour tracabilite
    # mais n'est plus utilise en prediction.
    cal_path = MODELS_DIR / "calibrator_v3_osrm.pkl"
    calibrator = joblib.load(cal_path) if cal_path.exists() else None
    MODEL_VERSION = "v3_osrm"
    print(f"Modele V3 OSRM charge : {len(features)} features (calibrator desactive)")
```

### 5.3 Conservation du fichier calibrator

Le fichier `calibrator_v3_osrm.pkl` n'a pas été supprimé. Justifications :
- Traçabilité de l'expérimentation
- Possibilité d'évaluer d'autres méthodes de calibration ultérieurement
- Aucun coût (~10 MB) de stockage

---

## 6. Validation

### 6.1 Tests automatisés

Exécution `pytest tests/ -v` après modification :

============================= 34 passed, 3 warnings in 7.53s ==============================

Tous les tests pytest restent verts (34/34), y compris les 5 tests de cohérence métier (frontale > arrière, aucun équipement > ceinture, etc.).

### 6.2 Validation empirique par scénarios métier

Trois scénarios représentatifs ont été testés en live sur Streamlit (avec restauration des pickles d'origine d'abord, pour garantir des conditions identiques à l'évaluation du notebook) :

| Scénario | Avec calibrator (avant) | Sans calibrator (après) | Cohérence métier |
|---|---:|---:|---|
| Ceinture + Frontale + Voiture ville | 49.6% Pas grave | 43.9% Pas grave | ✓ Cohérent (ceinture protège) |
| Aucun équipement + Collision arrière | 24.7% Pas grave | **60.4% GRAVE** | ✓ Cohérent (cas plus risqué) |
| Scénario extrême moto nuit autoroute verglacée | 67.5% Grave | **92.2% GRAVE** | ✓ Très cohérent (combinaison critique) |

**Constat** : sans calibrator, le modèle révèle des cas graves qui étaient masqués (cas n°2 : passage de 24.7% Pas grave à 60.4% Grave), et amplifie correctement les scénarios objectivement dangereux (cas n°3 : passage de 67.5% à 92.2%).

### 6.3 Métriques globales servies en production (après correction)

| Métrique | Valeur |
|---|---:|
| Recall GRAVE | 0.7643 |
| Precision GRAVE | 0.4166 |
| F1 macro | 0.6956 |
| AUC-ROC | 0.8558 |
| Accuracy | 0.7760 |

Ces chiffres correspondent désormais exactement à ce qui est mesuré dans le notebook 07 et à ce qui est annoncé dans le README et les rapports.

---

## 7. Impact et apprentissages

### 7.1 Impact métier

**Avant correction** : 67% des accidents réellement graves étaient classés "Pas grave" par le système. Pour un système d'aide à la décision en sécurité routière, cela aurait signifié que dans 2 cas sur 3 où une intervention prioritaire aurait été justifiée, le système ne l'aurait pas signalée.

**Après correction** : 76% des accidents réellement graves sont correctement détectés, en cohérence avec l'objectif métier (privilégier le rappel sur la classe critique, quitte à accepter plus de faux positifs).

### 7.2 Leçons techniques

**1. Toute composante de pipeline doit être évaluée empiriquement.** Un calibrator est généralement présenté dans la littérature comme une amélioration ; mais une bonne pratique théorique ne se vérifie qu'en mesurant son effet sur les données réelles du projet. L'absence d'évaluation a permis au bug de persister silencieusement pendant 8 jours.

**2. Les tests automatisés doivent couvrir les métriques de performance, pas seulement le fonctionnement technique.** Les 34 tests pytest étaient verts alors que le modèle servait des prédictions dégradées. Un test mesurant le Recall global sur un échantillon représentatif du test set aurait détecté la régression immédiatement.

**3. Méfiance vis-à-vis de l'Accuracy sur dataset déséquilibré.** L'accuracy passait de 77.6% à 85.5% avec le calibrator, ce qui aurait pu être interprété comme une amélioration. C'est le **paradoxe classique du déséquilibre** : un modèle qui prédit majoritairement la classe dominante gonfle l'accuracy mais rate la classe critique.

**4. Importance de la documentation technique des choix de pipeline.** Le calibrator avait été ajouté sans justification documentée ni évaluation. Une note technique aurait évité que ce composant passe inaperçu lors des revues de code.

### 7.3 Démarche méthodologique applicable

Cet incident illustre une démarche scientifique généralisable :

1. **Doute légitime sur une métrique annoncée** → vérification
2. **Identification du composant suspect** → lecture du code de production
3. **Évaluation empirique sur données réelles** → mesure des performances avant et après
4. **Décision argumentée par les chiffres** → suppression ou conservation
5. **Validation par scénarios métier** → confirmation que la correction améliore l'usage réel
6. **Documentation pour traçabilité** → ce document

### 7.4 Suites prévues

- Ajouter un test pytest mesurant le Recall global sur un échantillon représentatif (~100 cas) du test 2024, pour détecter automatiquement toute régression future.
- Inclure une cellule d'évaluation systématique de chaque composant ML (calibrators, transformateurs de features) dans les notebooks d'entraînement.
- Tester d'autres méthodes de calibration (sigmoid notamment) lors d'une itération future, en évaluant systématiquement leur effet sur les métriques métier.

---

## Annexes

### A. Référentiel des commits Git

| Commit | Date | Description |
|---|---|---|
| `02f12e6` | 14 mai 2026 | Désactivation du calibrator dans `routes_ia.py` + carnet de bord veille E2 |
| `e58eecd` | 14 mai 2026 | Mise à jour README avec vraies métriques V3 OSRM brut |

### B. Références notebook

| Notebook | Cellule (id) | Description |
|---|---|---|
| `notebook_07_modelisation_v3_osrm.ipynb` | `d62cf669` (cell 10) | Création du calibrator (sans évaluation) |
| `notebook_07_modelisation_v3_osrm.ipynb` | `9e3aad2e` (ajoutée 13/05) | Évaluation empirique du calibrator |

### C. Lignes de code modifiées

- `src/api/routes_ia.py:35-46` : note technique de désactivation
- `src/api/routes_ia.py:216` : remplacement du calibrator par le modèle brut

### D. Métriques de référence

Modèle servi en production après correction (LGBMClassifier V3 OSRM, sans calibration) :
- Test 2024 : 148 506 accidents
- Prévalence GRAVE : 17.15%
- Recall GRAVE : 0.7643 | Precision GRAVE : 0.4166 | F1 macro : 0.6956 | AUC-ROC : 0.8558
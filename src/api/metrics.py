"""
Definition des metriques Prometheus pour l'API RouteZone.
Expose des compteurs et histogrammes pour le monitoring temps reel.
"""
from prometheus_client import Counter, Histogram

# Compteur : nombre total de predictions faites
predictions_total = Counter(
    "routezone_predictions_total",
    "Nombre total de predictions effectuees",
    ["model_version"]  # label : on segmente par version de modele
)

# Compteur : nombre de predictions par classe (Grave / Pas grave)
predictions_par_classe = Counter(
    "routezone_predictions_par_classe_total",
    "Nombre de predictions par classe predite",
    ["label"]  # label : Grave ou Pas grave
)

# Histogramme : duree des predictions (latence)
prediction_duration = Histogram(
    "routezone_prediction_duration_seconds",
    "Duree d'une prediction en secondes",
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)  # plages de temps observees
)

# Compteur : nombre d'erreurs
errors_total = Counter(
    "routezone_errors_total",
    "Nombre total d'erreurs lors des predictions",
    ["error_type"]
)
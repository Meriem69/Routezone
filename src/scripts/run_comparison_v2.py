"""
Execute la comparaison Haversine V1 vs OSRM V2 (extrait des cellules
ajoutees a notebook_04, pour eviter d'avoir a re-tourner toute la
section Overpass API qui peut etre flaky).
Produit les visualisations dans visualisations/ et imprime le tableau
de stats + tests.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu, chi2_contingency

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "processed"
VIZ_DIR = ROOT / "notebooks" / "visualisations"
VIZ_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-darkgrid")

print("=" * 70)
print("COMPARAISON HAVERSINE V1 vs OSRM V2")
print("=" * 70)

osrm_path = DATA_DIR / "temps_intervention_osrm.csv"
df_v2 = pd.read_csv(osrm_path)
print(f"\n[1/5] Accidents enrichis OSRM : {len(df_v2):,}")
print(df_v2[["nearest_pompiers_min_hav", "nearest_pompiers_min_osrm",
             "nearest_sau_min_hav", "nearest_sau_min_osrm",
             "temps_total_hav", "temps_total_osrm",
             "delta_total"]].describe().round(2))

# ---------------------------------------------------------------------------
# Distribution comparee
# ---------------------------------------------------------------------------
print(f"\n[2/5] Generation distributions comparees...")
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
pairs = [
    ("nearest_pompiers_min_hav", "nearest_pompiers_min_osrm", "Pompiers -> Accident"),
    ("nearest_sau_min_hav",      "nearest_sau_min_osrm",      "Accident -> SAU"),
    ("temps_total_hav",          "temps_total_osrm",          "Total prise en charge"),
]
for ax, (hcol, ocol, title) in zip(axes, pairs):
    ax.hist(df_v2[hcol].dropna(), bins=50, alpha=0.5, color="#3b82f6",
            label=f"Haversine x1.3 (med {df_v2[hcol].median():.1f} min)")
    ax.hist(df_v2[ocol].dropna(), bins=50, alpha=0.5, color="#dc2626",
            label=f"OSRM reel (med {df_v2[ocol].median():.1f} min)")
    ax.set_xlabel("Minutes")
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.set_xlim(0, df_v2[ocol].quantile(0.99))
plt.suptitle("Distribution des temps : Haversine vs OSRM", fontsize=13)
plt.tight_layout()
plt.savefig(VIZ_DIR / "viz_nb04_haversine_vs_osrm_distrib.png", dpi=150, bbox_inches="tight")
plt.close()

# ---------------------------------------------------------------------------
# Scatter + biais par tranche
# ---------------------------------------------------------------------------
print(f"[3/5] Scatter + biais par tranche...")
fig, axes = plt.subplots(1, 2, figsize=(16, 5))
sample = df_v2.dropna(subset=["temps_total_hav", "temps_total_osrm"]).sample(
    min(20000, len(df_v2)), random_state=42)
axes[0].scatter(sample["temps_total_hav"], sample["temps_total_osrm"],
                s=2, alpha=0.25, c="#7c3aed")
mx = max(sample["temps_total_hav"].max(), sample["temps_total_osrm"].max())
axes[0].plot([0, mx], [0, mx], "k--", linewidth=1, label="y = x")
axes[0].set_xlabel("Haversine x 1.3 (min)")
axes[0].set_ylabel("OSRM reel (min)")
axes[0].set_title("Temps total : approximation vs realite")
axes[0].legend()

bins = [0, 5, 10, 15, 20, 30, 60, 200]
df_v2["tr_hav"] = pd.cut(df_v2["temps_total_hav"], bins=bins)
biais = df_v2.groupby("tr_hav", observed=False)["delta_total"].agg(["mean", "median", "count"]).round(2)
print(f"\nBiais OSRM - Haversine par tranche Haversine :")
print(biais)

axes[1].bar(range(len(biais)), biais["mean"], color="#dc2626", alpha=0.7)
axes[1].set_xticks(range(len(biais)))
axes[1].set_xticklabels([str(i) for i in biais.index], rotation=45, ha="right", fontsize=9)
axes[1].axhline(0, color="black", linestyle="--", linewidth=1)
axes[1].set_ylabel("OSRM - Haversine (min)")
axes[1].set_title("Biais moyen par tranche")
plt.tight_layout()
plt.savefig(VIZ_DIR / "viz_nb04_biais_par_tranche.png", dpi=150, bbox_inches="tight")
plt.close()

print(f"\nBiais moyen global    : {df_v2['delta_total'].mean():+.2f} min")
print(f"Biais median global   : {df_v2['delta_total'].median():+.2f} min")
print(f"Correlation Hav<->OSRM: {df_v2['temps_total_hav'].corr(df_v2['temps_total_osrm']):.3f}")

# ---------------------------------------------------------------------------
# Golden Hour V1 vs V2
# ---------------------------------------------------------------------------
print(f"\n[4/5] Golden Hour V1 vs V2 sur graves...")
df_full = pd.read_csv(DATA_DIR / "dataset_clean.csv", low_memory=False)
key = "Num_Acc" if "Num_Acc" in df_full.columns else "num_acc"
df_full = df_full.merge(df_v2, left_on=key, right_on="Num_Acc", how="inner")
graves_v2 = df_full[df_full["grav"].isin([2, 3])].copy()
graves_v2["deces"] = (graves_v2["grav"] == 2).astype(int)
print(f"Graves : {len(graves_v2):,}  (deces : {graves_v2['deces'].sum():,})")

bins = [0, 5, 10, 15, 20, 30, 45, 60, 300]
labs = ["0-5", "5-10", "10-15", "15-20", "20-30", "30-45", "45-60", "60+"]
graves_v2["tr_hav"] = pd.cut(graves_v2["temps_total_hav"], bins=bins, labels=labs)
graves_v2["tr_osrm"] = pd.cut(graves_v2["temps_total_osrm"], bins=bins, labels=labs)

print(f"\n{'Tranche':<10}{'Hav %deces':>14}{'(n)':>10}{'OSRM %deces':>16}{'(n)':>10}")
print("-" * 60)
for lab in labs:
    sh = graves_v2[graves_v2["tr_hav"] == lab]
    so = graves_v2[graves_v2["tr_osrm"] == lab]
    print(f"{lab:<10}{sh['deces'].mean()*100:>13.1f}%{len(sh):>10,}"
          f"{so['deces'].mean()*100:>15.1f}%{len(so):>10,}")

fig, axes = plt.subplots(1, 2, figsize=(16, 5), sharey=True)
colors_grad = ["#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444",
               "#dc2626", "#991b1b", "#450a0a"]
for ax, col, title in [
    (axes[0], "tr_hav",  "Haversine x 1.3 (V1)"),
    (axes[1], "tr_osrm", "OSRM reel (V2)"),
]:
    taux = graves_v2.groupby(col, observed=False)["deces"].agg(["mean", "count"])
    taux.columns = ["taux", "n"]
    taux = taux[taux["n"] > 0]
    bars = ax.bar(range(len(taux)), taux["taux"] * 100,
                  color=colors_grad[:len(taux)], edgecolor="white")
    ax.set_xticks(range(len(taux)))
    ax.set_xticklabels(taux.index, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Taux deces (%)")
    ax.set_title(title)
    ax.axhline(graves_v2["deces"].mean() * 100, color="black", linestyle="--", alpha=0.5)
    for bar, (_, row) in zip(bars, taux.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"n={int(row['n']):,}", ha="center", fontsize=7, color="gray")
plt.suptitle("Golden Hour : Haversine vs OSRM (taux de deces parmi blesses graves)", fontsize=13)
plt.tight_layout()
plt.savefig(VIZ_DIR / "viz_nb04_golden_hour_v1_vs_v2.png", dpi=150, bbox_inches="tight")
plt.close()

# ---------------------------------------------------------------------------
# Tests statistiques
# ---------------------------------------------------------------------------
print(f"\n[5/5] Tests statistiques :")
for col, label in [("temps_total_hav", "V1 Haversine x 1.3"),
                   ("temps_total_osrm", "V2 OSRM reel")]:
    sub = graves_v2.dropna(subset=[col])
    tab = pd.crosstab(sub[col] > 30, sub["deces"])
    chi2, pval, _, _ = chi2_contingency(tab)
    tues = sub[sub["deces"] == 1][col]
    hosp = sub[sub["deces"] == 0][col]
    _, pmw = mannwhitneyu(tues, hosp, alternative="greater")
    print(f"\n{label}")
    print(f"  Chi2 (>30 min vs deces) : chi2={chi2:.1f}, p={pval:.2e}")
    print(f"  Mann-Whitney            : median tues={tues.median():.1f}, hosp={hosp.median():.1f}, p={pmw:.2e}")

print(f"\nVisualisations sauvegardees dans {VIZ_DIR}")
print("DONE")

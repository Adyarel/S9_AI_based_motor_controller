# ------------------------------------------------------------ #
# Description : Python envoie une consigne PWM à un modèle Simulink
#               (via matlab_bridge.py), récupère les mesures simulées
#               et les écrit dans un CSV du même format que clean_csv_...
#
# Lancement :
#   python simulation_moteur.py modele_moteur 15 1.5
#   python simulation_moteur.py modele_moteur 15 1.5 --ref clean_csv_xxx.csv
#   (modèle sans .slx, consigne en %, durée en s)
#
# Utilisation dans un script :
#   from simulation_moteur import simuler_vers_csv
#   simuler_vers_csv("modele_moteur", pwm_pct=15, duree=1.5)
# ------------------------------------------------------------ #

# -------------------------Librairie---------------------------- #
import argparse
import csv
import os
from datetime import datetime

import numpy as np

from matlab_bridge import MatlabBridge, lire_csv, SEPARATEUR

# ---------------------------Paramètres--------------------------- #
TE = 0.0011985              # période d'échantillonnage du courant (s), comme sur le moteur réel
DECALAGE_VITESSE = 0.00059925   # la vitesse est mesurée ~Te/2 après le courant
PWM_MAX = 799               # pwm_valeur = 799 <-> 100 %  (120 <-> 15,02 %)

NOM_VAR_CONSIGNE = "pwm_pct"    # variable lue par le modèle Simulink (bloc Constant / Step)
COL_COURANT = 0                 # colonne de y_sim : bloc Out1 = courant (A)
COL_VITESSE = 1                 # colonne de y_sim : bloc Out2 = vitesse (rad/s)

EN_TETE = ["temps_courant_s", "courant_A", "temps_vitesse_s",
           "vitesse_rad_s", "pwm_valeur", "pwm_pct", "date"]


# ---------------------------Fonctions---------------------------- #
def simuler_vers_csv(modele, pwm_pct, duree, dossier_sortie=".", fichier_ref=None, session=None):
    """Envoie la consigne à Simulink, simule, et écrit le CSV des mesures simulées.

    fichier_ref : CSV mesuré dont on réutilise les temps (courant et vitesse),
                  pour comparer point à point. Sinon grille régulière (TE, DECALAGE_VITESSE).
    Retourne le chemin du CSV créé."""
    # 1) Python -> MATLAB -> Simulink -> Python
    with MatlabBridge(session=session) as m:
        t_sim, y_sim = m.simuler(modele, duree, **{NOM_VAR_CONSIGNE: float(pwm_pct)})
    t_sim = np.asarray(t_sim, dtype=float).ravel()
    y_sim = np.asarray(y_sim, dtype=float)
    if y_sim.ndim == 1:
        y_sim = y_sim.reshape(-1, 1)
    if y_sim.shape[1] <= max(COL_COURANT, COL_VITESSE):
        raise ValueError(f"le modèle renvoie {y_sim.shape[1]} sortie(s) : il faut des blocs Out "
                         f"pour le courant (Out{COL_COURANT + 1}) et la vitesse (Out{COL_VITESSE + 1})")

    # 2) Grilles de temps : celles du fichier mesuré, ou régulières
    if fichier_ref:
        ref = lire_csv(fichier_ref)
        t_i, t_w = ref["temps_courant"], ref["temps_vitesse"]
    else:
        t_i = np.arange(0.0, duree, TE)
        t_w = t_i + DECALAGE_VITESSE

    # 3) Rééchantillonnage des signaux simulés sur ces grilles
    courant = np.interp(t_i, t_sim, y_sim[:, COL_COURANT])
    vitesse = np.interp(t_w, t_sim, y_sim[:, COL_VITESSE])

    # 4) Écriture du CSV (même format que clean_csv_...)
    maintenant = datetime.now()
    pwm_valeur = int(round(pwm_pct * PWM_MAX / 100))
    nom = f"sim_csv_moteur_PWM{int(round(pwm_pct))}pct_{maintenant:%Y%m%d_%H%M%S}.csv"
    chemin = os.path.join(dossier_sortie, nom)
    date = maintenant.strftime("%Y-%m-%d %H:%M:%S")
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=SEPARATEUR)
        w.writerow(EN_TETE)
        for a, b, c, d in zip(t_i, courant, t_w, vitesse):
            w.writerow([f"{a:.9f}", f"{b:.6f}", f"{c:.9f}", f"{d:.4f}",
                        pwm_valeur, f"{pwm_pct:.2f}", date])
    print(f"{len(t_i)} points simulés écrits dans {chemin}")
    return chemin


# ----------------------------Lancement--------------------------- #
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Simulation Simulink pilotée par Python -> CSV")
    p.add_argument("modele", help="nom du modèle Simulink, sans .slx")
    p.add_argument("pwm_pct", type=float, help="consigne PWM en %%")
    p.add_argument("duree", type=float, help="durée de simulation en s")
    p.add_argument("--ref", default=None, help="CSV mesuré dont on reprend les temps")
    p.add_argument("--session", default=None, help="'auto' pour une session MATLAB partagée")
    a = p.parse_args()
    simuler_vers_csv(a.modele, a.pwm_pct, a.duree, fichier_ref=a.ref, session=a.session)

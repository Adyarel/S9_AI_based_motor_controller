# ------------------------------------------------------------ #
# Description : Python envoie la consigne PWM, MATLAB simule et écrit le CSV,
#               Python relit le CSV simulé.
#
# Lancement :
#   python lancer_simulation.py modele_moteur 15 1.5
#   (modèle sans .slx, consigne en %, durée en s)
#
# Prérequis : simuler_moteur.m dans le dossier MatLab (celui de matlab_bridge.py)
# ------------------------------------------------------------ #

# -------------------------Librairie---------------------------- #
import os
import sys

from matlab_bridge import MatlabBridge, lire_csv

# ---------------------------Paramètres--------------------------- #
DOSSIER_SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulations")


# ---------------------------Fonction----------------------------- #
def simuler(modele, pwm_pct, duree, dossier_sortie=DOSSIER_SORTIE, session=None):
    """Envoie la consigne à MATLAB, qui simule et écrit le CSV.
    Retourne (chemin_csv, donnees) ; donnees = dictionnaire de lire_csv()."""
    os.makedirs(dossier_sortie, exist_ok=True)
    with MatlabBridge(session=session) as m:
        chemin = m.appeler("simuler_moteur", modele, float(pwm_pct), float(duree),
                           os.path.abspath(dossier_sortie))
    return chemin, lire_csv(chemin)


# ----------------------------Lancement--------------------------- #
if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage : python lancer_simulation.py modele pwm_pct duree")
    chemin, donnees = simuler(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
    print("CSV simulé :", chemin)
    print(f"{len(donnees['courant'])} points, "
          f"courant final = {donnees['courant'][-1]:.4f} A, "
          f"vitesse finale = {donnees['vitesse'][-1]:.2f} rad/s")

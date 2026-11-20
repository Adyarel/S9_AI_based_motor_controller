# ------------------------------------------------------------ #
# Auteur : LOUINEAU Ronan - GE5
# Date : 09/11/26
# Fichier : campagne_essais_moteur.py
# Description : Automatisation du balayage de la PWM de 10% à 100%
# ------------------------------------------------------------ #

import time
import os

# Import de la fonction principale depuis votre script
from acquisition_moteur_v3 import acquisition 

# ------------------------------------------------------------ #
# --- Paramètres de la campagne ---
PWM_DEBUT = 20
PWM_FIN = 100
PAS_PWM = 2

DUREE_MESURE_S = 1.5  # Durée d'acquisition pour chaque palier
REPOS_ENTRE_ESSAIS_S = 0  # Temps pour laisser le moteur s'arrêter complètement
# ------------------------------------------------------------ #

DOSSIER_BRUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv", "brut") # dossier des CSV bruts
DOSSIER_CLEAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv", "clean")

def lancer_campagne(pwm_debut=PWM_DEBUT, pwm_fin=PWM_FIN, pas_pwm=PAS_PWM, duree_mesure_s=DUREE_MESURE_S, repos_entre_essai_s=REPOS_ENTRE_ESSAIS_S, dossier_brut=DOSSIER_BRUT, dossier_clean=DOSSIER_CLEAN):
    print(f"=== Début de la campagne d'essais : PWM de {pwm_debut}% à {pwm_fin}% (pas de {pas_pwm}%) ===")

    for pwm in range(pwm_debut, pwm_fin + 1, pas_pwm):
        print(f"\n[{time.strftime('%H:%M:%S')}] --- Lancement de l'essai pour PWM = {pwm}% ---")

        try:
            acquisition(
                pwm_pct=pwm,
                duree_s=duree_mesure_s,
                repos_s=repos_entre_essai_s,
                dossier_brut=dossier_brut,
                dossier_clean=dossier_clean,
            )

        except Exception as e:
            print(f"Erreur inattendue lors de l'essai à {pwm}% : {e}")
            print("Poursuite avec la valeur suivante...")

    print("\n=== Campagne d'essais terminée avec succès ===")
    print("Tous les fichiers CSV ont été générés dans les dossiers correspondants.")

if __name__ == "__main__":
    lancer_campagne()
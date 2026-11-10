# ------------------------------------------------------------ #
# Auteur : LOUINEAU Ronan - GE5
# Date : 10/11/26
# Description : Automatisation du balayage de la PWM de 10% à 100%
# ------------------------------------------------------------ #

import time
import random

# Import de la fonction principale depuis votre script
from acquisition_moteur_v3 import acquisition 

# ------------------------------------------------------------ #
# --- Paramètres de la campagne ---
PWM_MIN = 25 # Valeur minimale de PWM pour faire tourner le moteur
PWM_MAX = 100 # Valeur maximum de PWM pour faire tourner le moteur

DUREE_MESURE_S = 1.5  # Durée d'acquisition pour chaque palier
REPOS_ENTRE_ESSAIS_S = 0  # Temps pour laisser le moteur s'arrêter complètement

NOMBRE_ESSAIS = 10  # Nombre d'essais à effectuer
# ------------------------------------------------------------ #

def lancer_campagne_random():
    print(f"=== Début de la campagne d'essais d'échelon random :avec MIN PWM {PWM_MIN}% àet MAX PWM {PWM_MAX}% ===")
    
    for i in range(NOMBRE_ESSAIS):
        
        pwm = random.randint(PWM_MIN, PWM_MAX)
        print(f"\n[{time.strftime('%H:%M:%S')}] --- Ehcelon de PWM = {pwm}% ---")
        
        try:
            # Appel direct de votre fonction existante
            # Le port série reste ouvert et réutilisé à chaque itération
            acquisition(
                pwm_pct=pwm, 
                duree_s=DUREE_MESURE_S, 
                repos_s=REPOS_ENTRE_ESSAIS_S
            )
            
        except Exception as e:
            print(f"Erreur inattendue lors de l'essai à {pwm}% : {e}")
            print("Poursuite avec la valeur suivante...")
            
    print("\n=== Campagne d'essais terminée avec succès ===")
    print("Tous les fichiers CSV ont été générés dans les dossiers correspondants.")

if __name__ == "__main__":
    lancer_campagne()
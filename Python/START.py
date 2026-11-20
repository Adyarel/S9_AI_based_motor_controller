# ------------------------------------------------------------ #
# Auteur : LOUINEAU Ronan - GE5
# Date : 19/11/26
# Description : Essai unique sauvegardé dans un sous-dossier dédié (nom_du_test/csv/brut et clean)
# ------------------------------------------------------------ #

import time
import os
from datetime import datetime

# Import de la fonction principale depuis votre script
from acquisition_moteur_v3 import acquisition 
from tracer_courbes_v2 import tracer
from gen_data_set import lancer_campagne

def start_1(pwm_prct, duree_s, nom_du_test, repos_s=0):
    repertoire_base = os.path.join(os.path.dirname(os.path.abspath(__name__)), nom_du_test, "csv")
    BRUT_DIR = os.path.join(repertoire_base, "brut")
    CLEAN_DIR = os.path.join(repertoire_base, "clean")

    # Récupération des chemins complets des FICHIERS générés
    chemin_brut, chemin_clean = acquisition(
        pwm_prct, duree_s, repos_s,
        dossier_brut=BRUT_DIR,
        dossier_clean=CLEAN_DIR
    )

    # On passe le fichier CSV (chemin_clean) et non le dossier (CLEAN_DIR)
    if chemin_clean is not None:
        tracer(chemin_clean)

    return chemin_brut, chemin_clean

def start_data_set(pwm_prct_debut=20,pwm_prct_fin=100,pas_pwm_info=10,duree_de_1_mesure_s=1.5,nom_du_test=None,repos_s=0,afficher_courbes=False):
    if nom_du_test is None:
        nom_du_test = datetime.now().strftime("dataset_%Y%m%d_%H%M%S")

    repertoire_base = os.path.join(os.path.dirname(os.path.abspath(__name__)), nom_du_test, "csv")
    BRUT_DIR = os.path.join(repertoire_base, "brut")
    CLEAN_DIR = os.path.join(repertoire_base, "clean")

    lancer_campagne(pwm_debut=pwm_prct_debut,pwm_fin=pwm_prct_fin,pas_pwm=pas_pwm_info,duree_mesure_s=duree_de_1_mesure_s,repos_entre_essai_s=repos_s,dossier_brut=BRUT_DIR,dossier_clean=CLEAN_DIR)

    if afficher_courbes and os.path.isdir(CLEAN_DIR):
        fichiers_csv = sorted(f for f in os.listdir(CLEAN_DIR) if f.endswith(".csv"))
        for fichier in fichiers_csv:
            tracer(os.path.join(CLEAN_DIR, fichier))
            

def aide_debut():
    print("""
========================================================================
                GUIDE D'UTILISATION - ACQUISITION MOTEUR
========================================================================
""")
    
def aide1():print("""
1) LANCER UNE SEULE MESURE (avec tracé automatique) :
    start_1(pwm_prct, duree_s, nom_du_test, repos_s=0)

    Paramètres :
    - pwm_prct    : consigne PWM en % (0 à 100)
    - duree_s     : durée de la mesure en secondes (ex: 2.0)
    - nom_du_test : nom du dossier de sauvegarde (ex: "moteur_3")
    - repos_s     : temps d'arrêt avant l'échelon en s (défaut : 0)

    Exemple :
    >>> start_1(50, 2, "moteur_3")

------------------------------------------------------------------------
""")

def aide2(): print("""
2) LANCER UNE CAMPAGNE COMPLÈTE (DATASET) :
    start_data_set(pwm_prct_debut=20, pwm_prct_fin=100, pas_pwm_info=10,
                duree_de_1_mesure_s=1.5, nom_du_test=None, repos_s=0,
                afficher_courbes=False)

    Paramètres :
    - pwm_prct_debut      : PWM de départ en % (défaut : 20)
    - pwm_prct_fin        : PWM de fin en % (défaut : 100)
    - pas_pwm_info        : pas entre deux essais en % (défaut : 10)
    - duree_de_1_mesure_s : durée de chaque mesure en s (défaut : 1.5)
    - nom_du_test         : nom du dossier (défaut : date/heure auto)
    - repos_s             : temps d'arrêt entre essais en s (défaut : 0)
    - afficher_courbes    : True pour tracer tous les CSV à la fin (défaut : False)

    Exemples :
    >>> start_data_set(30, 90, 10, 1.5, "moteur_3_pas10")
    >>> start_data_set(30, 90, 20, 1.5, "test_rapide", afficher_courbes=True)

------------------------------------------------------------------------
""")
def aide_fin():print("""
Astuce : tapez aide() pour réafficher ce menu, ou exit() pour quitter.
========================================================================
""")

def aide():
    aide_debut()
    aide1()
    aide2()
    aide_fin()
    
def aide_start_1():
    aide_debut()
    aide1()
    aide_fin()
    
def aide_start_data_set():
    aide_debut()
    aide2()
    aide_fin()

if __name__ == "__main__":
    aide()
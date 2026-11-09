# ------------------------------------------------------------ #
# Date : 05/11/26
# Description : convertit un CSV d'acquisition (valeurs brutes de l'ADC)
#               en CSV propre avec le courant en A et la vitesse en rad/s
# ------------------------------------------------------------ #

# ------------------------------------------------------------ #
# Utilisation :
#   1) python convertir_csv.py
#   2) coller le nom du fichier à convertir quand le programme le demande
#      (ou le glisser-déposer dans la fenêtre), puis Entrée
#   3) le fichier converti est créé dans le même dossier, avec "clean_csv_"
#      devant le nom d'origine :
#        moteur_PWM50pct_20261105_120152.csv
#        -> clean_csv_moteur_PWM50pct_20261105_120152.csv
#   Entrée sans rien écrire : quitter.
# ------------------------------------------------------------ #

# -------------------------Librairie---------------------------- #
import csv
import os

# ---------------------------Paramètres--------------------------- #
SEPARATEUR = ","        # le même que dans acquisition_moteur.py
VREF = 5.0              # tension de référence de l'ADC (AVcc) en V
RESOLUTION = 1023       # ADC 10 bits : 0..1023
GAIN_COURANT = 10.0     # capteur de courant : 10 V/A
GAIN_VITESSE = 1.0      # capteur de vitesse : 1 V/rad/s


# ---------------------------Fonction----------------------------- #
def convertir(chemin_entree):
    """Lit un CSV brut et crée clean_csv_<nom d'origine> dans le même dossier,
    avec courant_A et vitesse_rad_s à la place des valeurs brutes.
    Les colonnes temps_s, pwm_valeur, pwm_pct et date sont conservées."""
    dossier, nom = os.path.split(chemin_entree)
    chemin_sortie = os.path.join(dossier, "clean_csv_" + nom)

    with open(chemin_entree, newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f, delimiter=SEPARATEUR)
        lignes = list(lecteur)
        colonnes = lecteur.fieldnames or []

    for colonne in ("temps_s", "courant_brut", "vitesse_brut"):
        if colonne not in colonnes:
            raise ValueError(f"colonne '{colonne}' absente : ce n'est pas un fichier brut "
                             f"d'acquisition (colonnes trouvées : {colonnes})")

    autres = [c for c in colonnes if c not in ("temps_s", "courant_brut", "vitesse_brut")]
    volt_par_pas = VREF / RESOLUTION

    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f, delimiter=SEPARATEUR)
        ecrivain.writerow(["temps_s", "courant_A", "vitesse_rad_s"] + autres)
        for ligne in lignes:
            courant = int(ligne["courant_brut"]) * volt_par_pas / GAIN_COURANT
            vitesse = int(ligne["vitesse_brut"]) * volt_par_pas / GAIN_VITESSE
            ecrivain.writerow([ligne["temps_s"], f"{courant:.6f}", f"{vitesse:.4f}"]
                              + [ligne[c] for c in autres])

    return chemin_sortie, len(lignes)


# ----------------------------Lancement--------------------------- #
if __name__ == "__main__":
    print("Conversion des CSV bruts en A et rad/s")
    while True:
        # Les guillemets sont retirés : "Copier en tant que chemin" de Windows en ajoute
        saisie = input("\nNom du fichier à convertir (Entrée pour quitter) : ").strip().strip('"').strip("'")
        if not saisie:
            break
        if not os.path.isfile(saisie):
            print(f"Fichier introuvable : {saisie}\n"
                  f"(dossier actuel : {os.getcwd()} - lance le script depuis le dossier du fichier "
                  f"ou colle son chemin complet)")
            continue
        if os.path.basename(saisie).startswith("clean_csv_"):
            print("Ce fichier est déjà converti.")
            continue
        try:
            sortie, nb = convertir(saisie)
            print(f"{nb} points convertis -> {sortie}")
        except Exception as erreur:
            print(f"Erreur : {erreur}")
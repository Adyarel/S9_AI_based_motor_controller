# ------------------------------------------------------------ #
# Date : 05/11/26
# Description : trace le courant et la vitesse du moteur en fonction du temps
#               à partir d'un CSV converti (clean_csv_...)
# ------------------------------------------------------------ #

# ------------------------------------------------------------ #
# Utilisation :
#   1) python tracer_courbes.py
#   2) coller le nom du fichier clean_csv_... quand le programme le demande
#   3) la figure s'affiche ; elle est aussi enregistrée en image (PNG)
#      dans le même dossier : courbes_<nom du fichier>.png
#   Fermer la fenêtre de la figure puis Entrée sans rien écrire : quitter.
#
# Prérequis : pip install matplotlib
# ------------------------------------------------------------ #

# -------------------------Librairie---------------------------- #
import csv
import os

import matplotlib.pyplot as plt

# ---------------------------Paramètres--------------------------- #
SEPARATEUR = ","        # le même que dans acquisition_moteur.py


# ---------------------------Fonction----------------------------- #
def lire_csv(chemin):
    """Retourne (t_courant, courant, t_vitesse, vitesse, infos) à partir d'un CSV converti.
    Courant et vitesse ont chacun leur base de temps (mesures alternées)."""
    with open(chemin, newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f, delimiter=SEPARATEUR)
        colonnes = lecteur.fieldnames or []
        if "courant_brut" in colonnes:
            raise ValueError("ce fichier contient des valeurs brutes : "
                             "convertis-le d'abord avec convertir_csv.py")
        for colonne in ("temps_courant_s", "courant_A", "temps_vitesse_s", "vitesse_rad_s"):
            if colonne not in colonnes:
                raise ValueError(f"colonne '{colonne}' absente (colonnes trouvées : {colonnes})")
        lignes = list(lecteur)

    t_courant = [float(l["temps_courant_s"]) for l in lignes]
    courant = [float(l["courant_A"]) for l in lignes]
    t_vitesse = [float(l["temps_vitesse_s"]) for l in lignes]
    vitesse = [float(l["vitesse_rad_s"]) for l in lignes]

    infos = []
    if "pwm_pct" in colonnes:
        infos.append(f"PWM {lignes[0]['pwm_pct']} %")
    if "date" in colonnes:
        infos.append(lignes[0]["date"])
    return t_courant, courant, t_vitesse, vitesse, " - ".join(infos)


def tracer(chemin):
    """Trace courant et vitesse en fonction du temps, enregistre un PNG et l'affiche."""
    t_courant, courant, t_vitesse, vitesse, infos = lire_csv(chemin)

    fig, (ax_i, ax_w) = plt.subplots(2, 1, sharex=True, figsize=(10, 7))
    fig.suptitle(f"Échelon de tension - {infos}" if infos else "Échelon de tension")

    ax_i.plot(t_courant, courant, color="tab:red")
    ax_i.set_ylabel("Courant (A)")
    ax_i.grid(True)

    ax_w.plot(t_vitesse, vitesse, color="tab:blue")
    ax_w.set_ylabel("Vitesse (rad/s)")
    ax_w.set_xlabel("Temps (s)")
    ax_w.grid(True)

    fig.tight_layout()

    dossier, nom = os.path.split(chemin)
    sortie = os.path.join(dossier, "courbes_" + os.path.splitext(nom)[0] + ".png")
    fig.savefig(sortie, dpi=150)
    print(f"{len(t_courant)} points par grandeur tracés, image enregistrée : {sortie}")

    plt.show()


# ----------------------------Lancement--------------------------- #
if __name__ == "__main__":
    print("Tracé du courant et de la vitesse en fonction du temps")
    while True:
        # Les guillemets sont retirés : "Copier en tant que chemin" de Windows en ajoute
        saisie = input("\nNom du fichier clean_csv_... (Entrée pour quitter) : ").strip().strip('"').strip("'")
        if not saisie:
            break
        if not os.path.isfile(saisie):
            print(f"Fichier introuvable : {saisie}\n"
                  f"(dossier actuel : {os.getcwd()} - lance le script depuis le dossier du fichier "
                  f"ou colle son chemin complet)")
            continue
        try:
            tracer(saisie)
        except Exception as erreur:
            print(f"Erreur : {erreur}")
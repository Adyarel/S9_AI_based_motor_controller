"""Affichage de la MLI d'un échantillon enregistré dans un fichier CSV."""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


FICHIER_ECHANTILLONS = Path(__file__).resolve().parent / "echantillons.csv"


def plot_echantillon(numero_echantillon, filename=FICHIER_ECHANTILLONS, afficher=True):
    """Trace les paliers de MLI (%) en fonction du temps (ms).

    numero_echantillon : numéro de ligne du CSV, à partir de 1.
    Chaque ligne contient : nombre de commandes, durée_ms, MLI_pct, ...
    Les commandes se suivent sans pause. Retourne la figure et les axes ;
    afficher=False permet de préparer ou sauvegarder le tracé sans l'afficher.
    """
    if not isinstance(numero_echantillon, int) or numero_echantillon < 1:
        raise ValueError("Le numéro d'échantillon doit être un entier supérieur ou égal à 1.")

    with open(filename, newline="", encoding="utf-8") as fichier:
        for numero_ligne, ligne in enumerate(csv.reader(fichier), start=1):
            if numero_ligne == numero_echantillon:
                break
        else:
            raise ValueError(f"L'échantillon {numero_echantillon} n'existe pas dans {filename}.")

    try:
        valeurs = [int(valeur) for valeur in ligne]
    except ValueError as erreur:
        raise ValueError(f"La ligne {numero_echantillon} doit contenir des entiers.") from erreur

    if not valeurs or valeurs[0] < 1 or len(valeurs) != 1 + 2 * valeurs[0]:
        raise ValueError(f"Format invalide à la ligne {numero_echantillon} : nombre de commandes incohérent.")

    durees_ms = valeurs[1::2]
    mli_pct = valeurs[2::2]
    if any(duree <= 0 for duree in durees_ms):
        raise ValueError("Les durées des commandes doivent être strictement positives.")
    if any(mli < 0 or mli > 100 for mli in mli_pct):
        raise ValueError("La MLI doit être comprise entre 0 et 100 %.")

    temps_ms = [0]
    for duree in durees_ms:
        temps_ms.append(temps_ms[-1] + duree)

    figure, axes = plt.subplots()
    # Répéter la dernière valeur pour conserver le dernier palier jusqu'à sa fin.
    axes.step(temps_ms, mli_pct + [mli_pct[-1]], where="post")
    axes.set_title(f"MLI de l'échantillon {numero_echantillon}")
    axes.set_xlabel("Temps (ms)")
    axes.set_ylabel("MLI (%)")
    axes.set_xlim(0, temps_ms[-1])
    axes.set_ylim(-5, 105)
    axes.grid(True, alpha=0.3)
    figure.tight_layout()

    if afficher:
        plt.show()
    return figure, axes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numero", type=int, nargs="?", default=1,
                        help="Numéro de l'échantillon à afficher (à partir de 1).")
    parser.add_argument("--fichier", type=Path, default=FICHIER_ECHANTILLONS,
                        help="Chemin du fichier CSV d'échantillons.")
    args = parser.parse_args()
    plot_echantillon(args.numero, filename=args.fichier)

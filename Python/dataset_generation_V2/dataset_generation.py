"""Structure des essais en boucle ouverte pour le futur dataset.

Un échantillon est une séquence de commandes successives, sans pause implicite
entre elles. Les durées sont exprimées en millisecondes et la MLI en pour cent.
ce module permet de générer des échantillons aléatoires et de les sauvegarder dans un fichier csv.
"""

import random
from math import log, exp, floor
from dataclasses import asdict, dataclass
from pathlib import Path


def create_echantillon(commande_nb_min, commande_nb_max, duree_min_ms, duree_max_ms, pwm_min_pct, pwm_max_pct):
    """Crée un échantillon aléatoire de commandes successives.
    commande_nb_min : nombre minimum de commandes dans l'échantillon
    commande_nb_max : nombre maximum de commandes dans l'échantillon
    duree_min_ms : durée minimale d'une commande (ms)
    duree_max_ms : durée maximale d'une commande (ms)
    pwm_min_pct : PWM minimale (pourcentage)
    pwm_max_pct : PWM maximale (pourcentage)"""

    nb_commandes = random.randint(commande_nb_min, commande_nb_max)
    commandes = []
    for _ in range(nb_commandes):
        duree_ms = floor(exp(random.random() * (log(duree_max_ms) - log(duree_min_ms)) + log(duree_min_ms)))
        pwm_pct = random.randint(pwm_min_pct, pwm_max_pct)
        commandes.append((duree_ms, pwm_pct))
    
    return commandes


def save_echantillon(echantillon, filename):
    """Sauvegarde un échantillon à la fin d'un fichier csv"""
    with open(filename, "a") as f:
        f.write(f"{len(echantillon)}")
        for duree_ms, pwm_pct in echantillon:
            f.write(f",{duree_ms},{pwm_pct}")
        f.write("\n")


def create_echantillons(commande_nb_min, commande_nb_max, duree_min_ms, duree_max_ms, pwm_min_pct, pwm_max_pct, nb_echantillons, filename, output_dir):
    """Crée plusieurs échantillons et les sauvegarde dans un fichier csv"""
    chemin = Path(output_dir) / filename
    chemin.parent.mkdir(parents=True, exist_ok=True)
    for i in range(nb_echantillons):
        save_echantillon(
            create_echantillon(
                commande_nb_min, commande_nb_max,
                duree_min_ms, duree_max_ms, 
                pwm_min_pct, pwm_max_pct)
            , chemin)


def clear_echantillons(filename, output_dir):
    """Supprime le contenu du fichier d'échantillons"""
    chemin = Path(output_dir) / filename
    with open(chemin, "w") as f:
        f.write("")


if __name__ == "__main__":
    filename = "echantillons.csv"
    output_dir = Path(__file__).resolve().parent
 
    CLEAR_FILE = True
    if CLEAR_FILE:
        clear_echantillons(filename, output_dir)
    
    # Paramètres pour la génération d'échantillons
    commande_nb_min = 5
    commande_nb_max = 25
    duree_min_ms = 20
    duree_max_ms = 300
    pwm_min_pct = 0
    pwm_max_pct = 100
    nb_echantillons = 100


    create_echantillons(
        commande_nb_min, commande_nb_max,
        duree_min_ms, duree_max_ms,
        pwm_min_pct, pwm_max_pct,
        nb_echantillons, filename, output_dir)

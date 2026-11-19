"""
Ce progrramme permet de créer une campagne d'essais automatisée pour le moteur CC

Pour cela, il commence par créer un répertoire daté du jour et numéroté pour stocker les fichiers
CSV générés.
Il lance la génération des consignes de dataset à l'aide du programme dataset_commande_generation
pour chaque essai :
    Il transmet au programme acquisition_echantillon.py les différentes consignes de PWM et les durées
    correspondantes pour chaque essai.
    Le programme acquisition_echantillon.py se charge de l'acquisition des données du moteur pour chaque
    consigne de PWM et de durée, et sauvegarde les résultats dans des fichiers CSV.
"""

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from importlib import import_module
from pathlib import Path

if __package__:
    from .dataset_commande_generation import (
        create_echantillon, save_echantillon,
    )
else:
    from dataset_commande_generation import (
        create_echantillon, save_echantillon,
    )


DOSSIER_CAMPAGNES = Path(__file__).resolve().parent / "campagnes"


@dataclass(frozen=True)
class ParametresCampagne:
    """Réglages transmis au générateur ; durées en ms et PWM en %."""

    nb_echantillons: int = 100
    commande_nb_min: int = 5
    commande_nb_max: int = 25
    duree_min_ms: int = 20
    duree_max_ms: int = 300
    pwm_min_pct: int = 0
    pwm_max_pct: int = 100

    def __post_init__(self):
        if any(type(valeur) is not int for valeur in vars(self).values()):
            raise ValueError("Tous les paramètres doivent être des entiers.")
        if self.nb_echantillons < 1:
            raise ValueError("Il faut au moins un échantillon.")
        if not 1 <= self.commande_nb_min <= self.commande_nb_max:
            raise ValueError("Nombre de commandes invalide : 1 <= min <= max attendu.")
        if not 1 <= self.duree_min_ms <= self.duree_max_ms:
            raise ValueError("Durées invalides : 1 <= min <= max attendu (ms).")
        if not 0 <= self.pwm_min_pct <= self.pwm_max_pct <= 100:
            raise ValueError("PWM invalide : 0 <= min <= max <= 100 attendu.")


def creer_dossier_campagne(dossier_racine=DOSSIER_CAMPAGNES):
    """Crée campagne_AAAAMMJJ_NNN sans écraser une campagne existante."""
    dossier_racine = Path(dossier_racine)
    dossier_racine.mkdir(parents=True, exist_ok=True)
    prefixe = f"campagne_{date.today():%Y%m%d}"
    numero = 1
    while True:
        dossier = dossier_racine / f"{prefixe}_{numero:03d}"
        try:
            dossier.mkdir()
        except FileExistsError:
            numero += 1
        else:
            return dossier


def charger_acquisition():
    """Charge le module matériel uniquement pour une campagne réelle.

    Interface attendue dans acquisition_echantillon.py :
        acquisition_echantillon(commandes, fichier_sortie)

    commandes est une liste de couples (duree_ms, pwm_pct), à exécuter dans
    l'ordre sans pause entre les paliers. Le module écrit le CSV demandé et
    assure l'arrêt du moteur et la libération du port, même en cas d'erreur.
    """
    nom_module = f"{__package__}.acquisition_echantillon" if __package__ else "acquisition_echantillon"
    module = import_module(nom_module)
    fonction = getattr(module, "acquisition_echantillon", None)
    if not callable(fonction):
        raise RuntimeError(
            "acquisition_echantillon.py doit définir la fonction "
            "acquisition_echantillon(commandes, fichier_sortie). "
            "Utiliser --simulation pour générer uniquement les consignes."
        )
    return fonction


def lancer_campagne(parametres=None, dossier_racine=DOSSIER_CAMPAGNES,
                    simulation=False, acquisition_fn=None):
    """Génère les consignes et lance une acquisition par séquence complète.

    Retourne le dossier de la campagne. En simulation, seul consignes.csv
    est généré : aucune mesure moteur n'est créée. acquisition_fn permet
    d'injecter une acquisition pour les tests sans connexion à l'Arduino.
    """
    if parametres is None:
        parametres = ParametresCampagne()
    if not simulation:
        if acquisition_fn is None:
            acquisition_fn = charger_acquisition()
        if not callable(acquisition_fn):
            raise TypeError("acquisition_fn doit être une fonction d'acquisition.")

    dossier = creer_dossier_campagne(dossier_racine)
    fichier_consignes = dossier / "consignes.csv"
    echantillons = []
    for _ in range(parametres.nb_echantillons):
        commandes = create_echantillon(
            parametres.commande_nb_min, parametres.commande_nb_max,
            parametres.duree_min_ms, parametres.duree_max_ms,
            parametres.pwm_min_pct, parametres.pwm_max_pct,
        )
        save_echantillon(commandes, fichier_consignes)
        echantillons.append(commandes)

    print(f"Campagne : {dossier}")
    print(f"{len(echantillons)} séquences enregistrées dans {fichier_consignes.name}.")
    if simulation:
        print("Simulation terminée : consignes générées, sans acquisition moteur.")
        return dossier

    dossier_mesures = dossier / "mesures"
    dossier_mesures.mkdir()
    for numero, commandes in enumerate(echantillons, start=1):
        fichier_sortie = dossier_mesures / f"essai_{numero:04d}_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
        print(f"Essai {numero}/{len(echantillons)} : {len(commandes)} commandes, "
              f"durée totale {sum(duree for duree, _ in commandes)} ms.")
        try:
            acquisition_fn(commandes=commandes, fichier_sortie=fichier_sortie)
            if not fichier_sortie.is_file():
                raise RuntimeError(f"Le CSV attendu n'a pas été créé : {fichier_sortie}")
        except Exception as erreur:
            raise RuntimeError(
                f"Campagne interrompue à l'essai {numero} : {erreur}. "
                f"Les consignes et résultats déjà écrits sont conservés dans {dossier}."
            ) from erreur

    print(f"Campagne terminée : {len(echantillons)} essais enregistrés.")
    return dossier


def main():
    parseur = argparse.ArgumentParser(description="Campagne automatisée d'essais du moteur CC.")
    parseur.add_argument("--simulation", action="store_true",
                         help="Générer les consignes sans connexion au moteur.")
    parseur.add_argument("--nombre", type=int, default=100,
                         help="Nombre d'essais (défaut : 100).")
    parseur.add_argument("--dossier", type=Path, default=DOSSIER_CAMPAGNES,
                         help="Répertoire dans lequel créer la campagne.")
    args = parseur.parse_args()
    try:
        lancer_campagne(ParametresCampagne(nb_echantillons=args.nombre),
                        dossier_racine=args.dossier, simulation=args.simulation)
    except (ValueError, RuntimeError, OSError) as erreur:
        parseur.exit(1, f"Erreur : {erreur}\n")


if __name__ == "__main__":
    main()

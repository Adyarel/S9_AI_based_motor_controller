"""Tests de campagne sans port série ni moteur connecté."""

import csv
import io
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from Python.dataset_generation_V2 import dataset_generation as campagne


class CampagneTests(unittest.TestCase):
    def setUp(self):
        racine = Path(__file__).resolve().parents[3] / "build" / "dataset-validation"
        racine.mkdir(parents=True, exist_ok=True)
        temporaire = tempfile.TemporaryDirectory(dir=racine)
        self.addCleanup(temporaire.cleanup)
        self.racine = Path(temporaire.name)
        self.parametres = campagne.ParametresCampagne(nb_echantillons=3)
        sortie = redirect_stdout(io.StringIO())
        sortie.__enter__()
        self.addCleanup(sortie.__exit__, None, None, None)

    def lire_consignes(self, dossier):
        with (dossier / "consignes.csv").open(newline="", encoding="utf-8") as fichier:
            lignes = [[int(champ) for champ in ligne] for ligne in csv.reader(fichier)]
        for ligne in lignes:
            self.assertEqual(len(ligne), 1 + 2 * ligne[0])
        return [list(zip(ligne[1::2], ligne[2::2])) for ligne in lignes]

    def test_simulation_genere_uniquement_les_consignes(self):
        with patch.object(campagne, "charger_acquisition") as charger:
            dossier = campagne.lancer_campagne(
                self.parametres, self.racine, simulation=True,
            )
        charger.assert_not_called()
        sequences = self.lire_consignes(dossier)
        self.assertEqual(len(sequences), 3)
        for commandes in sequences:
            self.assertTrue(5 <= len(commandes) <= 25)
            for duree, pwm in commandes:
                self.assertTrue(20 <= duree <= 300)
                self.assertTrue(0 <= pwm <= 100)
        self.assertEqual([f.name for f in dossier.iterdir()], ["consignes.csv"])

    def test_numerotation_sans_ecrasement(self):
        premier = campagne.lancer_campagne(self.parametres, self.racine, simulation=True)
        contenu = (premier / "consignes.csv").read_bytes()
        deuxieme = campagne.lancer_campagne(self.parametres, self.racine, simulation=True)
        self.assertEqual(premier.name, f"campagne_{date.today():%Y%m%d}_001")
        self.assertEqual(deuxieme.name, f"campagne_{date.today():%Y%m%d}_002")
        self.assertEqual((premier / "consignes.csv").read_bytes(), contenu)

    def test_transmission_des_sequences_et_destinations(self):
        appels = []

        def acquisition_simulee(commandes, fichier_sortie):
            appels.append((commandes, fichier_sortie))
            fichier_sortie.write_text("mesures_simulees_pour_test\n", encoding="utf-8")

        dossier = campagne.lancer_campagne(
            self.parametres, self.racine, acquisition_fn=acquisition_simulee,
        )
        self.assertEqual([commandes for commandes, _ in appels], self.lire_consignes(dossier))
        self.assertEqual(len(appels), 3)
        for numero, (_, destination) in enumerate(appels, start=1):
            self.assertEqual(destination.parent, dossier / "mesures")
            self.assertRegex(destination.name, rf"^essai_{numero:04d}_\d{{8}}_\d{{6}}_\d{{6}}\.csv$")
            self.assertTrue(destination.is_file())

    def test_erreur_acquisition_interrompt_et_conserve_les_resultats(self):
        appels = []

        def acquisition_simulee(commandes, fichier_sortie):
            appels.append(commandes)
            if len(appels) == 2:
                raise OSError("Liaison série interrompue")
            fichier_sortie.write_text("mesures_simulees_pour_test\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "interrompue à l'essai 2") as contexte:
            campagne.lancer_campagne(
                self.parametres, self.racine, acquisition_fn=acquisition_simulee,
            )
        self.assertIsInstance(contexte.exception.__cause__, OSError)
        self.assertEqual(len(appels), 2)
        dossier = next(self.racine.iterdir())
        self.assertEqual(len(self.lire_consignes(dossier)), 3)
        self.assertEqual(len(list((dossier / "mesures").glob("*.csv"))), 1)

    def test_absence_csv_ne_signale_pas_un_succes(self):
        with self.assertRaises(RuntimeError) as contexte:
            campagne.lancer_campagne(
                self.parametres, self.racine, acquisition_fn=lambda **kwargs: None,
            )
        self.assertIn("CSV attendu", str(contexte.exception.__cause__))

    def test_module_acquisition_vide_explique_le_branchement_manquant(self):
        with patch.object(campagne, "import_module", return_value=SimpleNamespace()):
            with self.assertRaisesRegex(RuntimeError, "doit définir la fonction"):
                campagne.lancer_campagne(self.parametres, self.racine)
        self.assertEqual(list(self.racine.iterdir()), [])

    def test_parametres_invalides(self):
        for valeurs in (
            {"nb_echantillons": 0}, {"nb_echantillons": True},
            {"commande_nb_min": 0}, {"commande_nb_min": 26},
            {"duree_min_ms": 0}, {"duree_max_ms": 19},
            {"pwm_min_pct": -1}, {"pwm_max_pct": 101}, {"pwm_min_pct": 101},
        ):
            with self.subTest(valeurs=valeurs), self.assertRaises(ValueError):
                campagne.ParametresCampagne(**valeurs)

    def test_lancement_script_et_module(self):
        depot = Path(__file__).resolve().parents[3]
        for nom, arguments in (
            ("script", [str(depot / "Python" / "dataset_generation_V2" / "dataset_generation.py")]),
            ("module", ["-m", "Python.dataset_generation_V2.dataset_generation"]),
        ):
            with self.subTest(nom=nom):
                destination = self.racine / nom
                resultat = subprocess.run(
                    [sys.executable, *arguments, "--simulation", "--nombre", "2",
                     "--dossier", str(destination)],
                    cwd=depot if nom == "module" else self.racine,
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(resultat.returncode, 0, resultat.stderr)
                dossier = next(destination.iterdir())
                self.assertEqual(len(self.lire_consignes(dossier)), 2)


if __name__ == "__main__":
    unittest.main()
